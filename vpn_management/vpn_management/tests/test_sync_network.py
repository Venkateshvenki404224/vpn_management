# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""sync_network: five independent gates, and an UPSERT that can never wipe."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import allocation, api
from vpn_management.vpn_management.tests import fixtures

TOKEN = "test-sync-token-123"


class TestSyncNetwork(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		frappe.db.set_single_value("VPN Settings", "sync_enabled", 1)
		frappe.db.set_single_value("VPN Settings", "sync_requires_local", 1)
		frappe.local.request_ip = "127.0.0.1"
		frappe.conf["vpn_sync_token"] = TOKEN

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.conf.pop("vpn_sync_token", None)
		frappe.local.request_ip = None

	def test_kill_switch_off_returns_audited_skipped(self):
		frappe.db.set_single_value("VPN Settings", "sync_enabled", 0)
		result = api.sync_network(token=TOKEN, interface_name="wg8")
		self.assertEqual(result["result"], "skipped")
		self.assertTrue(
			frappe.get_all("VPN Audit Log", filters={"action": "sync_network", "result": "skipped"})
		)

	def test_remote_ip_is_denied(self):
		frappe.local.request_ip = "8.8.8.8"
		with self.assertRaises(frappe.PermissionError):
			api.sync_network(token=TOKEN, interface_name="wg8")

	def test_wrong_token_is_denied(self):
		with self.assertRaises(frappe.PermissionError):
			api.sync_network(token="not-the-token", interface_name="wg8")

	def test_denied_attempt_records_a_failure_audit_row(self):
		with self.assertRaises(frappe.PermissionError):
			api.sync_network(token="not-the-token", interface_name="wg8")
		self.assertTrue(
			frappe.get_all("VPN Audit Log", filters={"action": "sync_network", "result": "failure"})
		)

	def test_missing_configured_token_fails_closed(self):
		frappe.conf.pop("vpn_sync_token", None)
		with self.assertRaises(frappe.PermissionError):
			api.sync_network(token="anything", interface_name="wg8")

	def test_non_sync_role_is_denied(self):
		fixtures.ensure_user("plain@vpn.test", ["VPN API"])
		frappe.set_user("plain@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			api.sync_network(token=TOKEN, interface_name="wg8")

	def test_vpn_sync_role_is_allowed(self):
		fixtures.ensure_user("syncbot@vpn.test", ["VPN Sync"])
		frappe.set_user("syncbot@vpn.test")
		with patch("frappe.enqueue"):
			result = api.sync_network(token=TOKEN, interface_name="wg8")
		self.assertEqual(result["result"], "synced")

	def test_vpn_admin_role_is_allowed(self):
		# Drives the SYNC_ROLES "VPN Admin" branch directly (no Administrator short-circuit).
		fixtures.ensure_user("vpnadmin@vpn.test", ["VPN Admin"])
		frappe.set_user("vpnadmin@vpn.test")
		with patch("frappe.enqueue"):
			result = api.sync_network(token=TOKEN, interface_name="wg8")
		self.assertEqual(result["result"], "synced")

	def test_sync_never_wipes_allocations_and_enqueues_upsert_and_reconcile(self):
		allocation.claim("wg8", None)
		before = frappe.db.count("IP Allocation", {"server": "wg8", "allocated": 1})
		self.assertEqual(before, 1)
		with patch("frappe.enqueue") as enqueue:
			api.sync_network(token=TOKEN, interface_name="wg8")
		after = frappe.db.count("IP Allocation", {"server": "wg8", "allocated": 1})
		self.assertEqual(after, before)  # sync itself never deletes an allocation
		methods = [call.args[0] for call in enqueue.call_args_list if call.args]
		self.assertIn("vpn_management.tasks.materialize_pool", methods)  # idempotent UPSERT
		self.assertIn("vpn_management.tasks.reconcile_interface", methods)
		row = frappe.get_all(
			"VPN Audit Log",
			filters={"action": "sync_network", "target": "wg8", "result": "success"},
			fields=["in_use_count_at_run"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(row[0].in_use_count_at_run, after)
