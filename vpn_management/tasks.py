# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Background reconcile, live-status poll, and self-heal for WireGuard interfaces.

Runs on the ``long`` queue (enqueued after commit by the controllers) and on the
scheduler. The DB is the source of truth: the full ``wg0.conf`` (Interface +
firewall PostUp/PostDown + every enabled Peer) is rendered from rows and the
running interface is converged to it. A ``config_hash`` short-circuits no-op
reconciles; a live interface is updated with diff-only ``wg syncconf`` (which
strips PostUp, so the REDIRECT never stacks) while the first bring-up runs the
firewall PostUp via ``wg-quick up``. ``poll_status`` reads ``wg show … dump``
back onto the peers; ``reconcile_all`` drift-corrects the fleet and re-converges
each interface from the DB after a restart. Every privileged action is audited.
"""

import datetime
import hashlib
import os
import tempfile
import time

import frappe
from frappe.query_builder import DocType
from frappe.utils import cint, convert_utc_to_system_timezone, now_datetime
from frappe.utils.password import get_decrypted_password, set_encrypted_password

from vpn_management import allocation, audit, crypto, firewall, privileged
from vpn_management.privileged import VpnAgentError

DEFAULT_WG_DIR = "/etc/wireguard"
DEFAULT_STALE_MINUTES = 5
SETTINGS = "VPN Settings"
# Real agent verb behind each audited action (argv is informational only).
_VERB_FOR_ACTION = {"provision": "up", "interface_up": "up", "peer_apply": "syncconf"}


def reconcile_interface(interface_name):
	"""Converge the live interface onto the DB (interface + firewall + peers)."""
	server = frappe.get_doc("WireGuard Server", interface_name)
	in_use = _in_use_count(interface_name)
	if not _egress_ready(server):
		_mark(server, status="Error")
		audit.record(
			"reconcile", interface_name, "skipped", detail="egress_interface is not set", in_use_count=in_use
		)
		return
	try:
		outcome = _converge(server)
	except Exception as error:
		# Any failure (render, keygen, or the agent call) degrades gracefully:
		# mark the row Error and leave the prior live interface untouched.
		_mark(server, status="Error")
		audit.record("reconcile", interface_name, "failure", detail=str(error), in_use_count=in_use)
		frappe.log_error(title="WireGuard reconcile failed", message=f"reconcile {server.name}: {error}")
		return
	if outcome is None:
		audit.record("reconcile", interface_name, "success", detail="no-op", in_use_count=in_use)
		return
	action, config_hash = outcome
	_mark(server, status="Up", provisioned=1, interface_up=1, config_hash=config_hash)
	_mark_peers_synced(server.name)
	argv = f"wg {_VERB_FOR_ACTION[action]} {interface_name}"
	audit.record(action, interface_name, "success", argv=argv, in_use_count=in_use)


def poll_status():
	"""Read live handshake/rx/tx back onto peers for every up interface."""
	for name in _server_names(interface_up=1):
		_poll_server(name)


def reconcile_all():
	"""Drift-correct the fleet: re-converge every enabled interface from the DB."""
	for name in _server_names(enabled=1):
		_correct_liveness_drift(name)
		reconcile_interface(name)


def materialize_pool(pool_name):
	"""Background entry point for pool materialization (see allocation.materialize)."""
	allocation.materialize(pool_name)


def _converge(server):
	"""Render and apply; return ``(action, config_hash)``, or None for a no-op."""
	_ensure_keypair(server)
	conf = _render_conf(server)
	config_hash = hashlib.sha256(conf.encode("utf-8")).hexdigest()
	if config_hash == server.config_hash and server.interface_up:
		frappe.logger("vpn_management").info(f"reconcile {server.name}: no-op (hash unchanged)")
		return None
	return _apply(server, conf), config_hash


def _apply(server, conf):
	# syncconf needs the interface already up (it ignores Address/PostUp); the
	# first bring-up therefore goes through wg-quick up (which runs the firewall
	# PostUp), every change after via diff-only wg syncconf (which strips PostUp,
	# so the never-torn-down REDIRECT cannot stack and live handshakes survive).
	path = _write_conf(server, conf)
	if server.interface_up:
		_agent("syncconf", [server.interface_name, path])
		return "peer_apply"
	_agent("up", [server.interface_name])
	return "provision" if not server.provisioned else "interface_up"


def _agent(verb, args):
	reply = privileged.call(verb, args)
	if not reply.get("ok"):
		raise VpnAgentError(reply.get("stderr") or reply.get("error") or f"wg {verb} failed")
	return reply


# --- live status poll ------------------------------------------------------


def _poll_server(name):
	in_use = _in_use_count(name)
	try:
		dump = _agent("show", [name, "dump"]).get("stdout", "")
	except VpnAgentError as error:
		audit.record("status_poll", name, "failure", detail=str(error), in_use_count=in_use)
		return
	summary = _apply_dump(name, dump)
	audit.record("status_poll", name, "success", detail=summary, in_use_count=in_use)


def _apply_dump(name, dump_text):
	by_key = _enabled_peers_by_key(name)
	threshold = _stale_threshold_seconds()
	clock = time.time()
	updated = stale = 0
	for row in _parse_dump(dump_text):
		peer = by_key.get(row["public_key"])
		if not peer:
			continue
		fresh = row["latest_handshake"] > 0 and (clock - row["latest_handshake"]) <= threshold
		frappe.db.set_value("VPN Peer", peer["name"], _peer_status(row, fresh))
		updated += 1
		stale += 0 if fresh else 1
	return f"{updated} peers updated, {stale} stale"


def _peer_status(row, fresh):
	updates = {
		"rx_bytes": row["rx_bytes"],
		"tx_bytes": row["tx_bytes"],
		"last_handshake": _epoch_to_datetime(row["latest_handshake"]),
		"status": "Active" if fresh else "Stale",
	}
	if row["endpoint"] and row["endpoint"] != "(none)":
		updates["endpoint"] = row["endpoint"]
	return updates


def _parse_dump(dump_text):
	"""Parse ``wg show <iface> dump`` peer lines (the first line is the iface)."""
	rows = []
	for line in dump_text.strip().splitlines()[1:]:
		fields = line.split("\t")
		if len(fields) < 7:
			continue
		rows.append(
			{
				"public_key": fields[0],
				"endpoint": fields[2],
				"latest_handshake": cint(fields[4]),
				"rx_bytes": cint(fields[5]),
				"tx_bytes": cint(fields[6]),
			}
		)
	return rows


def _epoch_to_datetime(epoch):
	# The wg dump handshake is a UTC epoch; Frappe stores/renders naive datetimes
	# in the SYSTEM timezone (like now_datetime), so convert before storing or the
	# Last Handshake reads skewed against every other timestamp on the row.
	if not epoch:
		return None
	utc = datetime.datetime.fromtimestamp(epoch, datetime.UTC).replace(tzinfo=None)
	return convert_utc_to_system_timezone(utc).replace(tzinfo=None)


def _stale_threshold_seconds():
	minutes = (
		cint(frappe.db.get_singles_dict(SETTINGS).get("status_poll_interval_min")) or DEFAULT_STALE_MINUTES
	)
	return minutes * 60


# --- self-heal -------------------------------------------------------------


def _correct_liveness_drift(name):
	"""Clear ``interface_up`` when the DB says up but the kernel disagrees.

	After a restart the kernel interface is gone while the DB still reads
	``interface_up = 1``; clearing it makes the reconcile branch back to a full
	``up`` (re-running the firewall PostUp) instead of a no-op.
	"""
	if not frappe.db.get_value("WireGuard Server", name, "interface_up"):
		return
	if _interface_is_live(name) is False:
		frappe.db.set_value("WireGuard Server", name, "interface_up", 0)


def _interface_is_live(name):
	"""True/False if the agent could be reached, None if it could not."""
	try:
		reply = privileged.call("show", [name])
	except VpnAgentError:
		return None
	return bool(reply.get("ok"))


# --- rendering -------------------------------------------------------------


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
	lines += [f"PostUp = {command}" for command in firewall.render_postup(server)]
	lines += [f"PostDown = {command}" for command in firewall.render_postdown(server)]
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


def _enabled_peers_by_key(interface_name):
	peers = frappe.get_all(
		"VPN Peer", filters={"server": interface_name, "enabled": 1}, fields=["name", "public_key"]
	)
	return {peer["public_key"]: peer for peer in peers}


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
	audit.record("keygen", server.name, "success", detail="generated server keypair")


# --- helpers ---------------------------------------------------------------


def _egress_ready(server):
	# The egress lives on the host (the host-net agent), not in this worker, so we
	# cannot probe its existence here; we guard only the misconfiguration the
	# design warns about — masquerading to a blank interface.
	return bool((server.egress_interface or "").strip())


def _in_use_count(interface_name):
	return frappe.db.count("IP Allocation", {"server": interface_name, "allocated": 1})


def _server_names(**filters):
	return [row["name"] for row in frappe.get_all("WireGuard Server", filters=filters, fields=["name"])]


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
