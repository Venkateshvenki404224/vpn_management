# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Dashboard aggregation: admin-gated counts, deltas, capacity, and trends — no key material."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import cstr, getdate

from vpn_management import audit, dashboard
from vpn_management.vpn_management.tests import fixtures


class TestDashboardSummary(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.ensure_user("viewer@vpn.test", ["VPN User"])
		dashboard._summary.clear_cache()

	def tearDown(self):
		frappe.set_user("Administrator")
		dashboard._summary.clear_cache()

	def _summary(self):
		# The aggregation is cached ~60s; clear it so each call reflects the
		# rows this test just created within its transaction.
		dashboard._summary.clear_cache()
		return dashboard.dashboard_summary()

	def test_shape_has_every_section(self):
		result = self._summary()
		for section in ("counts", "deltas", "servers", "ip_pool", "peers_per_day", "audit_per_day"):
			self.assertIn(section, result)
		for key in ("total", "active", "stale", "disabled", "revoked", "pending"):
			self.assertIsInstance(result["counts"][key], int)
			self.assertIsInstance(result["deltas"][key], int)
		for key in ("up", "down", "error", "total"):
			self.assertIsInstance(result["servers"][key], int)
		for key in ("total", "allocated", "reserved", "free"):
			self.assertIsInstance(result["ip_pool"][key], int)
		self.assertIsInstance(result["peers_per_day"], list)
		self.assertIsInstance(result["audit_per_day"], list)

	def test_counts_track_new_peers_by_status(self):
		before = self._summary()["counts"]
		fixtures.make_peer("wg8", peer_name="alice")
		revoked = fixtures.make_peer("wg8", peer_name="bob")
		frappe.db.set_value("VPN Peer", revoked.name, "status", "Revoked")
		after = self._summary()["counts"]
		self.assertEqual(after["total"], before["total"] + 2)
		self.assertEqual(after["pending"], before["pending"] + 1)
		self.assertEqual(after["revoked"], before["revoked"] + 1)

	def test_deltas_count_recent_provisioning(self):
		# Peers created "now" land in the recent 7-day window, so each lifts its delta.
		before = self._summary()["deltas"]
		fixtures.make_peer("wg8", peer_name="alice")
		fixtures.make_peer("wg8", peer_name="bob")
		after = self._summary()["deltas"]
		self.assertEqual(after["total"], before["total"] + 2)
		self.assertEqual(after["pending"], before["pending"] + 2)

	def test_server_counts_reflect_status(self):
		# setUp inserted one freshly created server (status defaults to "Down").
		servers = self._summary()["servers"]
		self.assertEqual(servers["total"], frappe.db.count("WireGuard Server"))
		self.assertGreaterEqual(servers["down"], 1)

	def test_ip_pool_tracks_allocation(self):
		before = self._summary()["ip_pool"]
		self.assertGreater(before["total"], 0)  # seed_pool materialized the /29
		fixtures.make_peer("wg8", peer_name="alice")  # claims one IP on insert
		after = self._summary()["ip_pool"]
		self.assertEqual(after["allocated"], before["allocated"] + 1)
		self.assertEqual(after["free"], before["free"] - 1)

	def test_trend_buckets_todays_peer(self):
		today = cstr(getdate())
		before = self._day_count(self._summary()["peers_per_day"], today)
		fixtures.make_peer("wg8", peer_name="carol")
		after = self._day_count(self._summary()["peers_per_day"], today)
		self.assertEqual(after, before + 1)

	def test_audit_per_day_groups_by_result(self):
		today = cstr(getdate())
		before = self._audit_count(self._summary()["audit_per_day"], today, "success")
		audit.record("reconcile", "wg8", "success")
		after = self._audit_count(self._summary()["audit_per_day"], today, "success")
		self.assertEqual(after, before + 1)

	@staticmethod
	def _day_count(rows, today):
		return next((row["count"] for row in rows if row["day"] == today), 0)

	@staticmethod
	def _audit_count(rows, today, result):
		return next((row["count"] for row in rows if row["day"] == today and row["result"] == result), 0)

	def test_admin_gated_for_non_admin(self):
		frappe.set_user("viewer@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			dashboard.dashboard_summary()

	def test_payload_carries_no_key_material(self):
		fixtures.make_peer("wg8", peer_name="dave")
		payload = frappe.as_json(self._summary())
		for secret in ("private_key", "preshared_key", "server_private_key"):
			self.assertNotIn(secret, payload)
