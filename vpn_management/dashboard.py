# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Read-only aggregation for the command-center dashboard.

A handful of grouped queries power the whole page: headline peer counts (with a
Δ-vs-prior-7-days trend per metric), the peer-status donut, server status counts,
an aggregate IP-pool capacity summary, and 30-day peers/day + audit-actions/day
time-series. Admin-gated, cached briefly, and the payload carries counts and
dates only — never any key material.
"""

import frappe
from frappe.query_builder import Case
from frappe.query_builder.functions import Count, Function, Sum
from frappe.utils import add_days, cint, cstr, getdate
from frappe.utils.caching import redis_cache

from vpn_management.permissions import is_admin

# Statuses surfaced as their own counters (mirrors the VPN Peer "status" select);
# anything outside this set still rolls into ``total``.
PEER_STATUSES = ("Active", "Stale", "Disabled", "Revoked", "Pending")
# WireGuard Server "status" select.
SERVER_STATUSES = ("Up", "Down", "Error")
TREND_DAYS = 30
# Window each stat-row Δ compares: the last 7 days against the 7 before that.
DELTA_DAYS = 7


@frappe.whitelist(methods=["GET"])
def dashboard_summary() -> dict:
	"""All command-center aggregations in one admin-only, key-free payload.

	Grouped queries instead of fetching every row to count in the browser. Returns
	counts, deltas, and dates — no key material ever leaves the server.
	"""
	_require_admin()
	return _summary()


def _require_admin() -> None:
	if not is_admin(frappe.session.user):
		frappe.throw(frappe._("Not permitted to view the dashboard summary."), frappe.PermissionError)


@redis_cache(ttl=60)
def _summary() -> dict:
	return {
		"counts": _counts_by_status(),
		"deltas": _stat_deltas(),
		"servers": _server_counts(),
		"ip_pool": _ip_pool(),
		"peers_per_day": _peers_per_day(),
		"audit_per_day": _audit_per_day(),
	}


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


def _stat_deltas() -> dict:
	"""Net peers created in the last 7 days minus the prior 7, per status (and total).

	One grouped pass using ``creation`` — the only time dimension peers carry — so
	each stat tile can show an ↑/↓ momentum arrow without a historical snapshot.
	"""
	peer = frappe.qb.DocType("VPN Peer")
	today = getdate()
	recent_start = add_days(today, -(DELTA_DAYS - 1))  # last 7 days incl. today
	prior_start = add_days(recent_start, -DELTA_DAYS)  # the 7 days before that
	recent = Sum(Case().when(peer.creation >= recent_start, 1).else_(0))
	prior = Sum(Case().when((peer.creation >= prior_start) & (peer.creation < recent_start), 1).else_(0))
	rows = (
		frappe.qb.from_(peer)
		.select(peer.status, recent.as_("recent"), prior.as_("prior"))
		.where(peer.creation >= prior_start)
		.groupby(peer.status)
		.run(as_dict=True)
	)
	deltas = {status.lower(): 0 for status in PEER_STATUSES}
	total = 0
	for row in rows:
		delta = cint(row.recent) - cint(row.prior)
		if row.status:
			deltas[row.status.lower()] = delta
		total += delta
	deltas["total"] = total
	return deltas


def _server_counts() -> dict:
	"""Count WireGuard Servers grouped by status (Up / Down / Error)."""
	server = frappe.qb.DocType("WireGuard Server")
	rows = (
		frappe.qb.from_(server)
		.select(server.status, Count(server.name).as_("count"))
		.groupby(server.status)
		.run(as_dict=True)
	)
	by_status = {row.status: row.count for row in rows}
	counts = {status.lower(): by_status.get(status, 0) for status in SERVER_STATUSES}
	counts["total"] = sum(by_status.values())
	return counts


def _ip_pool() -> dict:
	"""Aggregate IP-pool capacity across every pool (one indexed count pass).

	Mirrors ``infra._allocation_summary`` (total / allocated / reserved / free) but
	summed over all servers — a row is allocated XOR reserved XOR free, so free is
	the remainder.
	"""
	alloc = frappe.qb.DocType("IP Allocation")
	row = (
		frappe.qb.from_(alloc)
		.select(
			Count(alloc.name).as_("total"),
			Sum(alloc.allocated).as_("allocated"),
			Sum(alloc.reserved).as_("reserved"),
		)
		.run(as_dict=True)[0]
	)
	total, allocated, reserved = cint(row.total), cint(row.allocated), cint(row.reserved)
	return {
		"total": total,
		"allocated": allocated,
		"reserved": reserved,
		"free": max(total - allocated - reserved, 0),
	}


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


def _audit_per_day() -> list[dict]:
	"""Audit actions per calendar day, grouped by result, over ``TREND_DAYS``.

	Long format (one row per day+result); the dashboard pivots it into stacked
	success / failure / skipped series.
	"""
	log = frappe.qb.DocType("VPN Audit Log")
	day = Function("DATE", log.creation)
	since = add_days(getdate(), -(TREND_DAYS - 1))
	rows = (
		frappe.qb.from_(log)
		.select(day.as_("day"), log.result, Count(log.name).as_("count"))
		.where(log.creation >= since)
		.groupby(day, log.result)
		.orderby(day)
		.run(as_dict=True)
	)
	return [{"day": cstr(row.day), "result": row.result, "count": row.count} for row in rows]
