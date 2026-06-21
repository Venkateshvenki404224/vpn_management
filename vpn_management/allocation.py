# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""IP pool materialization and atomic per-peer address allocation.

The pool is *materialized*: every host address in a CIDR becomes an
``IP Allocation`` row whose ``name`` is ``{server}-{ip}``. Allocation is then a
single row-locked UPDATE of the lowest free row, which makes concurrent peer
creation safe and makes "is this address used" a plain column read. Rows are
upserted (``INSERT IGNORE``) and **never deleted** — re-materializing flips no
flags, which is the structural fix for the legacy ``deleteMany()`` wipe.
"""

import ipaddress

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import now

ALLOCATION = "IP Allocation"
_INSERT_FIELDS = (
	"name",
	"creation",
	"modified",
	"modified_by",
	"owner",
	"docstatus",
	"idx",
	"server",
	"pool",
	"ip_address",
	"ip_order",
	"allocated",
	"reserved",
)


def materialize(pool_name):
	"""Idempotently upsert an IP Allocation row for every host IP in the pool."""
	pool = frappe.get_cached_doc("Network Pool", pool_name)
	network = ipaddress.ip_network(pool.cidr, strict=False)
	gateway, intervals = _reserved_index(pool)
	rows = _allocation_rows(pool, network, gateway, intervals)
	frappe.db.bulk_insert(ALLOCATION, _INSERT_FIELDS, rows, ignore_duplicates=True)
	# INSERT IGNORE only creates missing rows, so reconcile the reserved flag on
	# existing free rows too — that is how a later gateway/reserved-range edit
	# takes effect. Allocated (in-use) rows are never touched.
	_reconcile_reserved(pool.name, gateway, intervals)
	frappe.db.set_value(
		"Network Pool",
		pool_name,
		{"total_addresses": len(rows), "last_materialized": now()},
	)


def claim(server, peer):
	"""Row-lock and allocate the lowest free address for ``server`` to ``peer``."""
	allocation = _lock_lowest_free(server)
	if not allocation:
		_throw_unavailable(server)
	frappe.db.set_value(
		ALLOCATION,
		allocation.name,
		{"allocated": 1, "peer": peer, "allocated_on": now()},
	)
	return allocation


def _throw_unavailable(server):
	if not frappe.db.exists(ALLOCATION, {"server": server}):
		frappe.throw(_("No address pool has been materialized for {0} yet.").format(server))
	frappe.throw(_("Address pool for {0} is exhausted.").format(server))


def _reconcile_reserved(pool_name, gateway, intervals):
	allocation = DocType(ALLOCATION)
	free = (allocation.pool == pool_name) & (allocation.allocated == 0)
	frappe.qb.update(allocation).set(allocation.reserved, 0).where(free).run()
	predicate = _reserved_predicate(allocation, gateway, intervals)
	if predicate is not None:
		frappe.qb.update(allocation).set(allocation.reserved, 1).where(free & predicate).run()


def _reserved_predicate(allocation, gateway, intervals):
	predicate = allocation.ip_order == gateway if gateway is not None else None
	for start, end in intervals:
		clause = (allocation.ip_order >= start) & (allocation.ip_order <= end)
		predicate = clause if predicate is None else (predicate | clause)
	return predicate


def release(allocation_name):
	"""Free an address (keep the row): ``allocated = 0`` and detach the peer."""
	frappe.db.set_value(ALLOCATION, allocation_name, {"allocated": 0, "peer": None})


def _lock_lowest_free(server):
	"""SELECT ... ORDER BY ip_order LIMIT 1 FOR UPDATE — the concurrency guard."""
	allocation = DocType(ALLOCATION)
	rows = (
		frappe.qb.from_(allocation)
		.select(allocation.name, allocation.ip_address)
		.where((allocation.server == server) & (allocation.allocated == 0) & (allocation.reserved == 0))
		.orderby(allocation.ip_order)
		.limit(1)
		.for_update()
	).run(as_dict=True)
	return rows[0] if rows else None


def _allocation_rows(pool, network, gateway, intervals):
	stamp = now()
	user = frappe.session.user
	rows = []
	for host in network.hosts():
		address = int(host)
		reserved = 1 if address == gateway or _in_any(address, intervals) else 0
		rows.append(
			(
				f"{pool.server}-{host}",
				stamp,
				stamp,
				user,
				user,
				0,
				0,
				pool.server,
				pool.name,
				str(host),
				address,
				0,
				reserved,
			)
		)
	return rows


def _reserved_index(pool):
	gateway = int(ipaddress.ip_address(pool.gateway_ip)) if pool.gateway_ip else None
	intervals = [
		(int(ipaddress.ip_address(r.start_ip)), int(ipaddress.ip_address(r.end_ip)))
		for r in pool.reserved_ranges
	]
	return gateway, intervals


def _in_any(address, intervals):
	return any(start <= address <= end for start, end in intervals)
