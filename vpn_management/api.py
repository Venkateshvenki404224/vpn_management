# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Token-authenticated REST surface for vpn_management.

Every endpoint is whitelisted with an explicit ``methods=`` and fully type-hinted
so Frappe casts each argument by its hint (which blocks type-confusion). There is
**no** ``allow_guest`` anywhere — callers authenticate with an API key/secret and
are gated by the four VPN roles. CRUD rides Frappe's document API (which honors
permissions and never serializes Password fields); responses are additionally
built from an explicit safe-field allowlist so no key material can ever leak.

``sync_network`` replaces the incident-causing ``/syncnetwork``. It is gated by
five independent checks and can only ever UPSERT (``INSERT IGNORE``) allocations,
never delete them — the legacy ``deleteMany()`` wipe class is structurally absent.
"""

import hmac
import ipaddress
import re

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.password import get_decrypted_password

from vpn_management import audit
from vpn_management.permissions import is_admin

SETTINGS = "VPN Settings"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
SYNC_ROLES = {"VPN Admin", "VPN Sync"}
SAFE_PEER_FIELDS = (
	"name",
	"peer_name",
	"owner_user",
	"server",
	"enabled",
	"public_key",
	"assigned_ip",
	"allowed_ips",
	"client_allowed_ips",
	"persistent_keepalive",
	"endpoint",
	"status",
	"synced_to_interface",
	"last_handshake",
	"rx_bytes",
	"tx_bytes",
)
SAFE_SERVER_FIELDS = (
	"name",
	"interface_name",
	"listen_port",
	"address_cidr",
	"server_public_key",
	"enabled",
	"provisioned",
	"status",
	"interface_up",
	"last_reconcile",
)


# --- peer CRUD -------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def create_peer(
	peer_name: str,
	server: str,
	public_key: str | None = None,
	owner_user: str | None = None,
	allowed_ips: str | None = None,
	persistent_keepalive: int | None = None,
) -> dict:
	"""Create a peer (IP allocated + reconcile enqueued by the controller)."""
	if not public_key and not is_admin(frappe.session.user):
		# Without permlevel-1 write a server-generated private key would be silently
		# reset on save, so non-admin callers must bring a client-generated key.
		frappe.throw(
			_("public_key is required: supply a client-generated public key."),
			frappe.ValidationError,
		)
	doc = frappe.new_doc("VPN Peer")
	doc.peer_name = peer_name
	doc.server = server
	doc.owner_user = _resolve_owner(owner_user)
	doc.public_key = public_key
	doc.allowed_ips = allowed_ips
	if persistent_keepalive is not None:
		doc.persistent_keepalive = persistent_keepalive
	doc.insert()
	return _peer_view(doc)


@frappe.whitelist(methods=["POST"])
def revoke_peer(name: str) -> dict:
	"""Soft-revoke a peer: free its address, drop it from the live interface."""
	doc = _readable_peer(name)
	doc.check_permission("write")
	doc.disable()
	frappe.db.set_value("VPN Peer", name, "status", "Revoked")
	doc.reload()
	return _peer_view(doc)


@frappe.whitelist(methods=["POST", "DELETE"])
def delete_peer(name: str) -> dict:
	"""Hard-delete a peer (on_trash frees the address and reconciles)."""
	frappe.delete_doc("VPN Peer", name)
	return {"deleted": name}


@frappe.whitelist(methods=["GET"])
def get_peer(name: str) -> dict:
	"""Return one peer the caller owns (admins unrestricted); no key material."""
	return _peer_view(_readable_peer(name))


@frappe.whitelist(methods=["GET"])
def list_peers(server: str | None = None, limit: int = 20, start: int = 0) -> list[dict]:
	"""List peers, owner-scoped for non-admins via permission_query_conditions."""
	filters = {"server": server} if server else {}
	return frappe.get_list(
		"VPN Peer",
		filters=filters,
		fields=list(SAFE_PEER_FIELDS),
		limit=cint(limit),
		limit_start=cint(start),
		order_by="creation desc",
	)


# --- doc-level mutations (delegate to whitelisted controller methods) -------


@frappe.whitelist(methods=["POST"])
def regenerate_keys(name: str) -> dict:
	"""Rotate a peer's keypair server-side; the private key never leaves the DB."""
	return _readable_peer(name).regenerate_keys()


# --- status ----------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def list_servers() -> list[dict]:
	"""List all servers (safe fields only) for the admin console — one query, no N+1."""
	return frappe.get_list(
		"WireGuard Server",
		fields=list(SAFE_SERVER_FIELDS),
		order_by="interface_name asc",
	)


@frappe.whitelist(methods=["GET"])
def interface_status(interface_name: str) -> dict:
	"""Return live interface status; never the server private key."""
	server = frappe.get_doc("WireGuard Server", interface_name)
	server.check_permission("read")
	return {field: server.get(field) for field in SAFE_SERVER_FIELDS}


@frappe.whitelist(methods=["GET"])
def get_peer_status(name: str) -> dict:
	"""Return a peer's live transfer/handshake status (owner-scoped)."""
	peer = _readable_peer(name)
	fields = ("name", "status", "assigned_ip", "endpoint", "last_handshake", "rx_bytes", "tx_bytes")
	return {field: peer.get(field) for field in fields}


# --- self-service portal (config + QR) -------------------------------------


@frappe.whitelist(methods=["GET"])
def my_config_download(name: str):
	"""Stream the caller's own peer as a ready-to-use WireGuard ``.conf``."""
	peer = _own_peer(name)
	frappe.response["filename"] = f"{_config_basename(peer)}.conf"
	frappe.response["filecontent"] = _render_client_config(peer)
	frappe.response["content_type"] = "text/plain; charset=utf-8"
	frappe.response["type"] = "download"


@frappe.whitelist(methods=["GET"])
def my_config_qr(name: str):
	"""Stream a QR PNG of the caller's own peer config (rendered inline)."""
	peer = _own_peer(name)
	frappe.response["filename"] = f"{_config_basename(peer)}.png"
	frappe.response["filecontent"] = _qr_png(_render_client_config(peer))
	frappe.response["content_type"] = "image/png"
	frappe.response["display_content_as"] = "inline"
	frappe.response["type"] = "download"


# --- interface lifecycle (VPN-Admin-gated by the write perm) ----------------


@frappe.whitelist(methods=["POST"])
def reconcile_interface(interface_name: str) -> dict:
	"""Converge the live interface from the DB (idempotent reconcile)."""
	return frappe.get_doc("WireGuard Server", interface_name).bring_up()


@frappe.whitelist(methods=["POST"])
def provision_server(interface_name: str) -> dict:
	"""Materialize the server's pools, then bring the interface up."""
	server = frappe.get_doc("WireGuard Server", interface_name)
	server.check_permission("write")
	_materialize_pools(interface_name)
	return server.bring_up()


# --- hardened sync_network -------------------------------------------------


@frappe.whitelist(methods=["POST"])
def sync_network(token: str, interface_name: str | None = None) -> dict:
	"""Idempotently re-converge the network behind five independent gates."""
	settings = frappe.db.get_singles_dict(SETTINGS)
	if not _flag(settings, "sync_enabled"):
		audit.record("sync_network", interface_name or "*", "skipped", detail="sync_enabled is off")
		return {"result": "skipped", "reason": "sync disabled"}
	_gate_local(settings)
	_gate_token(token)
	_gate_role()
	return _run_sync(interface_name)


def _gate_local(settings):
	if not _flag(settings, "sync_requires_local"):
		return
	if getattr(frappe.local, "request_ip", None) not in LOOPBACK:
		_deny("sync_network must originate from loopback")


def _gate_token(token):
	expected = frappe.conf.get("vpn_sync_token")
	if not expected or not hmac.compare_digest(str(token), str(expected)):
		_deny("invalid sync token")


def _gate_role():
	if frappe.session.user == "Administrator":
		return
	if not (SYNC_ROLES & set(frappe.get_roles())):
		_deny("sync_network requires the VPN Admin or VPN Sync role")


def _deny(message):
	audit.record("sync_network", "*", "failure", detail=message)
	# On a real HTTP request the PermissionError below makes the request handler
	# roll the transaction back (app.py: db.rollback on any exception), which would
	# discard the denial audit row; commit it first so denied attempts stay on record.
	# Skipped outside a request (tests/console/jobs commit at their own boundary).
	if getattr(frappe.local, "request", None):
		frappe.db.commit()  # nosemgrep -- deliberate: persist the denial audit past the request rollback
	frappe.throw(_(message), frappe.PermissionError)


def _run_sync(interface_name):
	names = [interface_name] if interface_name else _all_servers()
	return {"result": "synced", "servers": [_sync_server(name) for name in names]}


def _sync_server(name):
	# UPSERT only: materialize is INSERT IGNORE and never deletes, so the audit's
	# in_use_count_at_run proves no allocation was wiped by this run. Materialize is
	# enqueued (a /16 is ~65k rows) so heavy work never blocks the request — matching
	# provision_server.
	in_use = _in_use_count(name)
	_materialize_pools(name)
	_enqueue_reconcile(name)
	audit.record("sync_network", name, "success", in_use_count=in_use, detail=f"upsert ok, {in_use} in use")
	return {"server": name, "in_use_count": in_use}


# --- helpers ---------------------------------------------------------------


def _readable_peer(name):
	doc = frappe.get_doc("VPN Peer", name)
	doc.check_permission("read")
	return doc


def _own_peer(name):
	"""Fetch a peer the caller owns — the per-request ownership recheck.

	This is the fifth, independent isolation layer behind the portal: it never
	trusts the perm system (``get_doc`` does not enforce read perms), it compares
	``owner_user`` directly, so a forged ``name`` for someone else's peer is denied
	even if every other layer were misconfigured. Admins are unrestricted.
	"""
	peer = frappe.get_doc("VPN Peer", name)
	if not is_admin(frappe.session.user) and peer.owner_user != frappe.session.user:
		frappe.throw(_("You may only access your own VPN configuration."), frappe.PermissionError)
	return peer


def _render_client_config(peer):
	"""Render the peer's client-side WireGuard config from the live DB values."""
	host = _endpoint_host()
	if not host:
		frappe.throw(_("The VPN endpoint host is not configured; contact your administrator."))
	if not peer.assigned_ip:
		frappe.throw(_("This peer has no assigned address (it may be disabled)."))
	server = frappe.get_cached_doc("WireGuard Server", peer.server)
	lines = _client_interface_lines(peer) + _client_peer_lines(peer, server, host)
	return "\n".join(lines) + "\n"


def _client_interface_lines(peer):
	# The client's [Interface] carries the peer's own private key (server-generated
	# and stored encrypted) and its assigned address; a client-generated key is not
	# in the DB, so leave a placeholder the user fills in with the key they hold.
	private_key = get_decrypted_password("VPN Peer", peer.name, "private_key", raise_exception=False)
	lines = ["[Interface]"]
	lines.append(f"PrivateKey = {private_key}" if private_key else "# PrivateKey = <your client private key>")
	lines.append(f"Address = {peer.assigned_ip}/{_max_prefix(peer.assigned_ip)}")
	dns = (frappe.db.get_single_value(SETTINGS, "dns_servers") or "").strip()
	if dns:
		lines.append(f"DNS = {dns}")
	return lines


def _client_peer_lines(peer, server, host):
	# The client's [Peer] is the server itself: its public key, the public endpoint,
	# and what the client routes through the tunnel (client_allowed_ips).
	lines = ["", "[Peer]", f"PublicKey = {server.server_public_key}"]
	preshared_key = get_decrypted_password("VPN Peer", peer.name, "preshared_key", raise_exception=False)
	if preshared_key:
		lines.append(f"PresharedKey = {preshared_key}")
	lines.append(f"Endpoint = {_format_endpoint(host, server.listen_port)}")
	lines.append(f"AllowedIPs = {peer.client_allowed_ips or '0.0.0.0/0, ::/0'}")
	keepalive = cint(peer.persistent_keepalive)
	if keepalive:
		lines.append(f"PersistentKeepalive = {keepalive}")
	return lines


def _endpoint_host():
	settings = frappe.db.get_singles_dict(SETTINGS)
	host = settings.get("vpn_endpoint_host") or frappe.conf.get("vpn_endpoint_host")
	return (host or "").strip()


def _format_endpoint(host, port):
	# WireGuard requires IPv6 literal endpoints to be bracketed ([2001:db8::1]:port);
	# hostnames and IPv4 literals pass through unchanged.
	try:
		is_ipv6 = isinstance(ipaddress.ip_address(host), ipaddress.IPv6Address)
	except ValueError:
		is_ipv6 = False
	return f"[{host}]:{port}" if is_ipv6 else f"{host}:{port}"


def _max_prefix(address):
	# /32 for an IPv4 host, /128 for an IPv6 host — the assigned address is a single route.
	return ipaddress.ip_address(address).max_prefixlen


def _config_basename(peer):
	return re.sub(r"[^A-Za-z0-9_.-]", "_", peer.peer_name or peer.name)


def _qr_png(text):
	import io

	import qrcode

	image = qrcode.make(text)
	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	return buffer.getvalue()


def _resolve_owner(requested):
	user = frappe.session.user
	if requested and is_admin(user):
		return requested
	return user


def _peer_view(doc):
	return {field: doc.get(field) for field in SAFE_PEER_FIELDS}


def _materialize_pools(server):
	for pool in frappe.get_all("Network Pool", filters={"server": server}, pluck="name"):
		frappe.enqueue(
			"vpn_management.tasks.materialize_pool",
			queue="long",
			enqueue_after_commit=True,
			job_id=f"materialize-{pool}",
			deduplicate=True,
			pool_name=pool,
		)


def _enqueue_reconcile(interface_name):
	frappe.enqueue(
		"vpn_management.tasks.reconcile_interface",
		queue="long",
		enqueue_after_commit=True,
		job_id=f"reconcile-{interface_name}",
		deduplicate=True,
		interface_name=interface_name,
	)


def _all_servers():
	return frappe.get_all("WireGuard Server", pluck="name")


def _in_use_count(interface_name):
	return frappe.db.count("IP Allocation", {"server": interface_name, "allocated": 1})


def _flag(settings, field):
	# A single applies its JSON default only while unsaved; once any field is
	# stored a missing Check reads 0, so fall back to the declared default.
	value = settings.get(field)
	if value is None:
		value = frappe.get_meta(SETTINGS).get_field(field).default
	return bool(cint(value))
