# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Peer CRUD + live status.

Every response is built from :data:`SAFE_PEER_FIELDS` so a peer's ``private_key``
/``preshared_key`` (permlevel 1) can never be serialized back to the client. Reads
are owner-scoped for non-admins through ``permissions.permission_query_conditions``;
writes ride the ``VPN Peer`` controller (keygen, IP allocation, reconcile enqueue).
"""

import frappe
from frappe import _
from frappe.utils import cint

from vpn_management.permissions import is_admin

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


@frappe.whitelist(methods=["POST"])
def regenerate_keys(name: str) -> dict:
	"""Rotate a peer's keypair server-side; the private key never leaves the DB."""
	return _readable_peer(name).regenerate_keys()


@frappe.whitelist(methods=["GET"])
def get_peer_status(name: str) -> dict:
	"""Return a peer's live transfer/handshake status (owner-scoped)."""
	peer = _readable_peer(name)
	fields = ("name", "status", "assigned_ip", "endpoint", "last_handshake", "rx_bytes", "tx_bytes")
	return {field: peer.get(field) for field in fields}


# --- helpers ---------------------------------------------------------------


def _readable_peer(name):
	doc = frappe.get_doc("VPN Peer", name)
	doc.check_permission("read")
	return doc


def _resolve_owner(requested):
	user = frappe.session.user
	if requested and is_admin(user):
		return requested
	return user


def _peer_view(doc):
	return {field: doc.get(field) for field in SAFE_PEER_FIELDS}
