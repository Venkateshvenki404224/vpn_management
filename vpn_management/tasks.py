# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Background reconcile: converge a WireGuard Server row onto the live kernel.

Runs on the ``long`` queue (enqueued after commit by the controller). It is
idempotent — keys are generated only when missing, the conf is rendered
deterministically, and an already-live interface is left untouched. Socket or
render failures set ``status = Error`` loudly without crashing the worker.
"""

import os
import tempfile

import frappe
from frappe.utils import now_datetime
from frappe.utils.password import set_encrypted_password

from vpn_management import crypto, privileged
from vpn_management.privileged import VpnAgentError

DEFAULT_WG_DIR = "/etc/wireguard"


def provision_server(interface_name):
	"""Reconcile one WireGuard Server onto the host interface (idempotent)."""
	server = frappe.get_doc("WireGuard Server", interface_name)
	_ensure_keypair(server)
	try:
		_reconcile_interface(server)
	except (VpnAgentError, OSError) as error:
		_mark(server, status="Error", interface_up=0)
		frappe.log_error(title="WireGuard provisioning failed", message=f"provision {server.name}: {error}")
		return
	_mark(server, status="Up", provisioned=1, interface_up=1)


def _ensure_keypair(server):
	if server.get_password("server_private_key", raise_exception=False):
		return
	private_key, public_key = crypto.generate_keypair()
	set_encrypted_password("WireGuard Server", server.name, private_key, "server_private_key")
	frappe.db.set_value("WireGuard Server", server.name, "server_public_key", public_key)
	server.server_public_key = public_key


def _render_interface_conf(server):
	path = os.path.join(_wg_dir(), f"{server.interface_name}.conf")
	_atomic_write(path, _interface_block(server), 0o600)
	return path


def _interface_block(server):
	lines = [
		"[Interface]",
		f"PrivateKey = {server.get_password('server_private_key')}",
		f"Address = {server.address_cidr}",
		f"ListenPort = {server.listen_port}",
	]
	return "\n".join(lines) + "\n"


def _reconcile_interface(server):
	# Phase 1 brings the interface up once. If it is already live, leave it
	# untouched so re-saving is a true no-op. Applying config CHANGES to a live
	# interface (wg syncconf + config_hash diffing) is phase 2 — until then a
	# live interface keeps its first-provisioned config.
	if _interface_is_live(server.interface_name):
		return
	_render_interface_conf(server)
	_agent_up(server.interface_name)


def _interface_is_live(interface_name):
	reply = privileged.call("show", [])
	return interface_name in (reply.get("stdout") or "").split()


def _agent_up(interface_name):
	reply = privileged.call("up", [interface_name])
	if not reply.get("ok"):
		raise VpnAgentError(reply.get("stderr") or reply.get("error") or "wg-quick up failed")


def _mark(server, **fields):
	fields["last_reconcile"] = now_datetime()
	frappe.db.set_value("WireGuard Server", server.name, fields)


def _wg_dir():
	return frappe.db.get_single_value("VPN Settings", "wg_dir") or DEFAULT_WG_DIR


def _atomic_write(path, content, mode):
	directory = os.path.dirname(path)
	fd, tmp_path = tempfile.mkstemp(dir=directory)
	try:
		with os.fdopen(fd, "w") as handle:
			handle.write(content)
		os.chmod(tmp_path, mode)
		os.replace(tmp_path, path)
	except BaseException:
		if os.path.exists(tmp_path):
			os.unlink(tmp_path)
		raise
