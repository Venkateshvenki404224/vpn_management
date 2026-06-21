# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Hardened ``sync_network`` — the safe replacement for the incident-causing
``/syncnetwork``.

It is gated by five independent checks (kill-switch → loopback → constant-time
token → role → upsert-only) and can ONLY ever UPSERT (``INSERT IGNORE``)
allocations, never delete them: the legacy ``deleteMany()`` wipe class is
structurally absent. Denials are committed to the audit log before the request
rolls back, so refused attempts stay on record.
"""

import hmac

import frappe
from frappe import _
from frappe.utils import cint

from vpn_management import audit
from vpn_management.api.infra import materialize_pools

SETTINGS = "VPN Settings"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
SYNC_ROLES = {"VPN Admin", "VPN Sync"}


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
	materialize_pools(name)
	_enqueue_reconcile(name)
	audit.record("sync_network", name, "success", in_use_count=in_use, detail=f"upsert ok, {in_use} in use")
	return {"server": name, "in_use_count": in_use}


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
