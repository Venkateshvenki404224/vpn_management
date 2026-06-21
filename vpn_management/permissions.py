# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Row-level permission scoping for VPN Peer.

Non-admin callers (VPN User, VPN API) may only see peers they own. The list
query is narrowed with :func:`get_permission_query_conditions` and single-document
access is narrowed with :func:`has_permission`; both treat VPN Admin / System
Manager / Administrator as unrestricted. A controller ``has_permission`` hook can
only *deny* access that role perms already granted, so this never widens a role.
"""

import frappe

PEER = "VPN Peer"
ADMIN_ROLES = {"VPN Admin", "System Manager"}


def get_permission_query_conditions(user=None):
	"""Scope VPN Peer list queries to the caller's own peers (admins exempt)."""
	user = user or frappe.session.user
	if is_admin(user):
		return ""
	return f"`tab{PEER}`.`owner_user` = {frappe.db.escape(user)}"


def has_permission(doc, ptype=None, user=None, debug=False):
	"""Allow single VPN Peer access only to its owner (admins exempt)."""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	return doc.get("owner_user") == user


def is_admin(user):
	"""True for unrestricted callers: Administrator, System Manager, or VPN Admin."""
	if user == "Administrator":
		return True
	return bool(ADMIN_ROLES & set(frappe.get_roles(user)))
