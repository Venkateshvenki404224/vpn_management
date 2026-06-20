# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Background reconcile: converge a WireGuard interface onto its DB state.

Runs on the ``long`` queue (enqueued after commit by the controllers). The DB is
the source of truth: the full ``wg0.conf`` (Interface + every enabled Peer) is
rendered from rows, and the running interface is converged to it. A ``config_hash``
short-circuits no-op reconciles; a live interface is updated with diff-only
``wg syncconf`` so existing handshakes never flap. Socket/render failures set
``status = Error`` loudly without crashing the worker.
"""

import hashlib
import os
import tempfile

import frappe
from frappe.query_builder import DocType
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password, set_encrypted_password

from vpn_management import allocation, crypto, privileged
from vpn_management.privileged import VpnAgentError

DEFAULT_WG_DIR = "/etc/wireguard"


def reconcile_interface(interface_name):
	"""Converge the live interface onto the DB (interface + all enabled peers)."""
	server = frappe.get_doc("WireGuard Server", interface_name)
	try:
		config_hash = _converge(server)
	except Exception as error:
		# Any failure (render, keygen, or the agent call) degrades gracefully:
		# mark the row Error and leave the prior live interface untouched.
		_mark(server, status="Error")
		frappe.log_error(title="WireGuard reconcile failed", message=f"reconcile {server.name}: {error}")
		return
	if config_hash is None:
		return
	_mark(server, status="Up", provisioned=1, interface_up=1, config_hash=config_hash)
	_mark_peers_synced(server.name)


def _converge(server):
	"""Render and apply the interface; return the new config_hash, or None for a no-op."""
	_ensure_keypair(server)
	conf = _render_conf(server)
	config_hash = hashlib.sha256(conf.encode("utf-8")).hexdigest()
	if config_hash == server.config_hash and server.interface_up:
		frappe.logger("vpn_management").info(f"reconcile {server.name}: no-op (hash unchanged)")
		return None
	_apply(server, conf)
	return config_hash


def materialize_pool(pool_name):
	"""Background entry point for pool materialization (see allocation.materialize)."""
	allocation.materialize(pool_name)


def _apply(server, conf):
	# syncconf needs the interface already up (it ignores Address/PostUp); the
	# first bring-up therefore goes through wg-quick up, every change after via
	# diff-only wg syncconf so live handshakes are preserved.
	path = _write_conf(server, conf)
	if server.interface_up:
		_agent("syncconf", [server.interface_name, path])
	else:
		_agent("up", [server.interface_name])


def _agent(verb, args):
	reply = privileged.call(verb, args)
	if not reply.get("ok"):
		raise VpnAgentError(reply.get("stderr") or reply.get("error") or f"wg {verb} failed")
	return reply


def _render_conf(server):
	blocks = [_interface_block(server)]
	blocks.extend(_peer_block(peer) for peer in _enabled_peers(server.name))
	return "\n".join(blocks)


def _interface_block(server):
	lines = [
		"[Interface]",
		f"PrivateKey = {server.get_password('server_private_key')}",
		f"Address = {server.address_cidr}",
		f"ListenPort = {server.listen_port}",
	]
	return "\n".join(lines) + "\n"


def _peer_block(peer):
	lines = ["[Peer]", f"PublicKey = {peer.public_key}"]
	preshared_key = get_decrypted_password("VPN Peer", peer.name, "preshared_key", raise_exception=False)
	if preshared_key:
		lines.append(f"PresharedKey = {preshared_key}")
	lines.append(f"AllowedIPs = {peer.allowed_ips or f'{peer.assigned_ip}/32'}")
	return "\n".join(lines) + "\n"


def _enabled_peers(interface_name):
	# One query for the render fields; the preshared key (a Password) is fetched
	# per peer only when present — avoids loading a full doc per peer (N+1).
	return frappe.get_all(
		"VPN Peer",
		filters={"server": interface_name, "enabled": 1},
		fields=["name", "public_key", "allowed_ips", "assigned_ip"],
		order_by="name",
	)


def _mark_peers_synced(interface_name):
	peer = DocType("VPN Peer")
	(
		frappe.qb.update(peer)
		.set(peer.synced_to_interface, 1)
		.set(peer.status, "Active")
		.where((peer.server == interface_name) & (peer.enabled == 1))
	).run()


def _ensure_keypair(server):
	if server.get_password("server_private_key", raise_exception=False):
		return
	private_key, public_key = crypto.generate_keypair()
	set_encrypted_password("WireGuard Server", server.name, private_key, "server_private_key")
	frappe.db.set_value("WireGuard Server", server.name, "server_public_key", public_key)
	server.server_public_key = public_key


def _mark(server, **fields):
	fields["last_reconcile"] = now_datetime()
	frappe.db.set_value("WireGuard Server", server.name, fields)


def _wg_dir():
	return frappe.db.get_single_value("VPN Settings", "wg_dir") or DEFAULT_WG_DIR


def _write_conf(server, conf):
	path = os.path.join(_wg_dir(), f"{server.interface_name}.conf")
	_atomic_write(path, conf, 0o600)
	return path


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
