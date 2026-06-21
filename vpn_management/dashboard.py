# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Read-only aggregation for the admin dashboard.

One grouped query powers the headline peer counts and the 30-day provisioning
trend, so the SPA no longer fetches every peer just to count them client-side.
Admin-gated, cached briefly, and the payload carries counts and dates only —
never any key material.
"""

import frappe
from frappe.query_builder.functions import Count, Function
from frappe.utils import add_days, cstr, getdate
from frappe.utils.caching import redis_cache

from vpn_management.permissions import is_admin

# Statuses surfaced as their own counters (mirrors the VPN Peer "status" select);
# anything outside this set still rolls into ``total``.
PEER_STATUSES = ("Active", "Stale", "Disabled", "Revoked", "Pending")
TREND_DAYS = 30


@frappe.whitelist(methods=["GET"])
def dashboard_summary() -> dict:
	"""Peer counts by status plus a 30-day provisioning trend for the dashboard.

	A single grouped aggregation instead of fetching every peer to count them in
	the browser. Admin-only; returns counts and dates — no key material.
	"""
	_require_admin()
	return _summary()


def _require_admin() -> None:
	if not is_admin(frappe.session.user):
		frappe.throw(frappe._("Not permitted to view the dashboard summary."), frappe.PermissionError)


@redis_cache(ttl=60)
def _summary() -> dict:
	return {"counts": _counts_by_status(), "peers_per_day": _peers_per_day()}


def _counts_by_status() -> dict:
	"""Count peers grouped by status in one query (no per-status round trips)."""
	peer = frappe.qb.DocType("VPN Peer")
	rows = (
		frappe.qb.from_(peer)
		.select(peer.status, Count(peer.name).as_("count"))
		.groupby(peer.status)
		.run(as_dict=True)
	)
	by_status = {row.status: row.count for row in rows}
	counts = {status.lower(): by_status.get(status, 0) for status in PEER_STATUSES}
	counts["total"] = sum(by_status.values())
	return counts


def _peers_per_day() -> list[dict]:
	"""Peers created per calendar day over the trailing ``TREND_DAYS`` window."""
	peer = frappe.qb.DocType("VPN Peer")
	day = Function("DATE", peer.creation)
	since = add_days(getdate(), -(TREND_DAYS - 1))
	rows = (
		frappe.qb.from_(peer)
		.select(day.as_("day"), Count(peer.name).as_("count"))
		.where(peer.creation >= since)
		.groupby(day)
		.orderby(day)
		.run(as_dict=True)
	)
	return [{"day": cstr(row.day), "count": row.count} for row in rows]
