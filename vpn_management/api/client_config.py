# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Self-service portal endpoints: stream a peer's own ``.conf`` and its QR PNG.

These render the *client-side* config from the live DB. The server's private key is
never rendered — only its public key — and access is gated by :func:`_own_peer`, an
independent per-request ownership recheck that does not trust the perm system.
"""

import ipaddress
import re

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.password import get_decrypted_password

from vpn_management.permissions import is_admin

SETTINGS = "VPN Settings"


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


# --- helpers ---------------------------------------------------------------


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
