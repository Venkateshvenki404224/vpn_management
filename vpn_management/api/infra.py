# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Infrastructure CRUD: WireGuard Servers, Network Pools, and the IP map.

Admin-gated read+write wrappers over the core document API. Each response is built
from an explicit safe-field allowlist so ``server_private_key`` (permlevel 1) can
never reach the client, and writes ride the controllers (keygen, validation,
materialize/reconcile enqueue) rather than bypassing them.
"""

import frappe
from frappe.utils import cint

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
# The editable subset surfaced to the form (key material is never in here).
SERVER_FORM_FIELDS = ("interface_name", "listen_port", "environment", "address_cidr", "egress_interface")
SAFE_FIREWALL_FIELDS = ("rule_type", "ip_table", "chain", "spec", "teardown_on_down", "enabled")
SAFE_POOL_FIELDS = (
	"name",
	"pool_name",
	"server",
	"cidr",
	"gateway_ip",
	"host_increment_strategy",
	"total_addresses",
	"last_materialized",
)
SAFE_RESERVED_FIELDS = ("start_ip", "end_ip", "reason")


# --- servers ---------------------------------------------------------------


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
def get_server(interface_name: str) -> dict:
	"""Return one server with its firewall rules for the edit form; no key material."""
	server = frappe.get_doc("WireGuard Server", interface_name)
	server.check_permission("read")
	return _server_detail(server)


@frappe.whitelist(methods=["POST"])
def upsert_server(
	interface_name: str,
	listen_port: int | None = None,
	environment: str | None = None,
	address_cidr: str | None = None,
	egress_interface: str | None = None,
	firewall_rules: list | None = None,
) -> dict:
	"""Create or edit a WireGuard Server (admin-gated); the response hides key material."""
	is_new = not frappe.db.exists("WireGuard Server", interface_name)
	if is_new:
		server = frappe.new_doc("WireGuard Server")
		server.interface_name = interface_name
	else:
		server = frappe.get_doc("WireGuard Server", interface_name)
		server.check_permission("write")
	_apply_fields(
		server,
		{
			"listen_port": listen_port,
			"environment": environment,
			"address_cidr": address_cidr,
			"egress_interface": egress_interface,
		},
	)
	rows = _coerce_rows(firewall_rules)
	if rows is not None:
		_set_child_rows(server, "firewall_rules", rows, SAFE_FIREWALL_FIELDS)
		# The caller passed an explicit rule set (possibly [] = "no rules"); don't let
		# before_insert re-seed the defaults over it on create.
		server.flags.skip_firewall_seed = True
	server.insert() if is_new else server.save()
	return _server_detail(server)


# --- pools -----------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def list_pools(server: str | None = None) -> list[dict]:
	"""List network pools (safe fields), optionally scoped to one server — one query."""
	filters = {"server": server} if server else {}
	return frappe.get_list(
		"Network Pool", filters=filters, fields=list(SAFE_POOL_FIELDS), order_by="pool_name asc"
	)


@frappe.whitelist(methods=["GET"])
def get_pool(pool_name: str) -> dict:
	"""Return one pool with its reserved ranges for the edit form."""
	pool = frappe.get_doc("Network Pool", pool_name)
	pool.check_permission("read")
	return _pool_detail(pool)


@frappe.whitelist(methods=["POST"])
def upsert_pool(
	pool_name: str,
	server: str,
	cidr: str,
	gateway_ip: str | None = None,
	host_increment_strategy: str | None = None,
	reserved_ranges: list | None = None,
) -> dict:
	"""Create or edit a Network Pool (admin-gated); materialize is enqueued by the controller."""
	is_new = not frappe.db.exists("Network Pool", pool_name)
	if is_new:
		pool = frappe.new_doc("Network Pool")
		pool.pool_name = pool_name
	else:
		pool = frappe.get_doc("Network Pool", pool_name)
		pool.check_permission("write")
	pool.server = server
	pool.cidr = cidr
	_apply_fields(pool, {"gateway_ip": gateway_ip, "host_increment_strategy": host_increment_strategy})
	rows = _coerce_rows(reserved_ranges)
	if rows is not None:
		_set_child_rows(pool, "reserved_ranges", rows, SAFE_RESERVED_FIELDS)
	pool.insert() if is_new else pool.save()
	return _pool_detail(pool)


# --- IP allocation map -----------------------------------------------------


@frappe.whitelist(methods=["GET"])
def list_ip_allocations(server: str, limit: int = 512, start: int = 0) -> dict:
	"""Return a server's IP allocation map (summary counts + a page of rows).

	A /16 materializes ~65k rows, so the grid pages through them while the summary
	(cheap indexed counts) always reflects the whole pool. No key material here.
	"""
	frappe.get_doc("WireGuard Server", server).check_permission("read")
	# Gate rows (permission-aware get_list) AND summary (raw db.count) behind one IP
	# Allocation read check so they can't disagree, and clamp the page size: a falsy
	# limit (cint(0)/cint("x")==0) would otherwise drop the LIMIT and stream a whole
	# /16 (~65k rows) into one response.
	frappe.has_permission("IP Allocation", "read", throw=True)
	page = min(max(cint(limit) or 512, 1), 1000)
	offset = max(cint(start), 0)
	rows = frappe.get_list(
		"IP Allocation",
		filters={"server": server},
		fields=["name", "ip_address", "allocated", "reserved", "peer"],
		order_by="ip_order asc",
		limit=page,
		limit_start=offset,
	)
	return {
		"server": server,
		"summary": _allocation_summary(server),
		"rows": rows,
		"limit": page,
		"start": offset,
	}


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
	materialize_pools(interface_name)
	return server.bring_up()


# --- helpers ---------------------------------------------------------------


def _server_detail(server):
	view = {field: server.get(field) for field in SAFE_SERVER_FIELDS}
	view.update({field: server.get(field) for field in SERVER_FORM_FIELDS})
	view["firewall_rules"] = [
		{field: row.get(field) for field in SAFE_FIREWALL_FIELDS} for row in server.firewall_rules
	]
	return view


def _pool_detail(pool):
	view = {field: pool.get(field) for field in SAFE_POOL_FIELDS}
	view["reserved_ranges"] = [
		{field: row.get(field) for field in SAFE_RESERVED_FIELDS} for row in pool.reserved_ranges
	]
	return view


def _apply_fields(doc, values):
	# Set only the fields the caller actually sent; ``None`` means "leave as is" so an
	# edit form can omit a field, while "" is a real value (e.g. clears the gateway).
	for field, value in values.items():
		if value is not None:
			doc.set(field, value)


def _coerce_rows(value):
	# Child-table args arrive as a JSON string over HTTP; None means "don't touch the
	# table", [] means "clear it". Parse once into a plain list of dicts.
	if value is None:
		return None
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return list(value or [])


def _set_child_rows(doc, fieldname, rows, allowed_fields):
	doc.set(fieldname, [])
	for row in rows:
		doc.append(fieldname, {field: row.get(field) for field in allowed_fields if field in row})


def _allocation_summary(server):
	total = frappe.db.count("IP Allocation", {"server": server})
	allocated = frappe.db.count("IP Allocation", {"server": server, "allocated": 1})
	reserved = frappe.db.count("IP Allocation", {"server": server, "reserved": 1})
	return {"total": total, "allocated": allocated, "reserved": reserved, "free": max(total - allocated - reserved, 0)}


def materialize_pools(server):
	"""Enqueue an idempotent materialize for each of a server's pools (shared with sync)."""
	for pool in frappe.get_all("Network Pool", filters={"server": server}, pluck="name"):
		frappe.enqueue(
			"vpn_management.tasks.materialize_pool",
			queue="long",
			enqueue_after_commit=True,
			job_id=f"materialize-{pool}",
			deduplicate=True,
			pool_name=pool,
		)
