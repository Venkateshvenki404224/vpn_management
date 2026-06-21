# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Self-service VPN portal served at ``/vpn``.

A logged-in VPN User sees **only the peers they own** and downloads each peer's
ready-to-use WireGuard ``.conf`` / QR (rendered by :mod:`vpn_management.api`).
The owner-scoped query here is the first of five independent isolation layers
(the others live in :mod:`vpn_management.permissions` and the download
endpoints); it never selects any key material.
"""

from urllib.parse import quote

import frappe
from frappe import _

PEER = "VPN Peer"
SETTINGS = "VPN Settings"
# Display fields only — never private_key / preshared_key.
PORTAL_FIELDS = ("name", "peer_name", "server", "assigned_ip", "status", "last_handshake")


def get_context(context):
	_reject_guest()
	context.no_cache = 1
	context.endpoint_ready = _endpoint_ready()
	context.peers = _owned_peers()
	return context


def _reject_guest():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to access your VPN configurations."), frappe.PermissionError)


def _owned_peers():
	peers = frappe.get_all(
		PEER,
		filters={"owner_user": frappe.session.user, "enabled": 1},
		fields=list(PORTAL_FIELDS),
		order_by="creation desc",
	)
	for peer in peers:
		peer["conf_url"] = _endpoint("my_config_download", peer["name"])
		peer["qr_url"] = _endpoint("my_config_qr", peer["name"])
	return peers


def _endpoint(method, name):
	return f"/api/method/vpn_management.api.{method}?name={quote(name)}"


def _endpoint_ready():
	settings = frappe.db.get_singles_dict(SETTINGS)
	return bool(settings.get("vpn_endpoint_host") or frappe.conf.get("vpn_endpoint_host"))
