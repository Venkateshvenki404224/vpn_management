# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Dashboard aggregation: admin-gated counts + 30-day trend, no key material."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import cstr, getdate

from vpn_management import dashboard
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
		# peers this test just created within its transaction.
		dashboard._summary.clear_cache()
		return dashboard.dashboard_summary()

	def test_shape_has_counts_and_trend(self):
		result = self._summary()
		self.assertIn("counts", result)
		self.assertIn("peers_per_day", result)
		for key in ("total", "active", "stale", "disabled", "revoked", "pending"):
			self.assertIsInstance(result["counts"][key], int)
		self.assertIsInstance(result["peers_per_day"], list)

	def test_counts_track_new_peers_by_status(self):
		before = self._summary()["counts"]
		fixtures.make_peer("wg8", peer_name="alice")
		revoked = fixtures.make_peer("wg8", peer_name="bob")
		frappe.db.set_value("VPN Peer", revoked.name, "status", "Revoked")
		after = self._summary()["counts"]
		self.assertEqual(after["total"], before["total"] + 2)
		self.assertEqual(after["pending"], before["pending"] + 1)
		self.assertEqual(after["revoked"], before["revoked"] + 1)

	def test_trend_buckets_todays_peer(self):
		today = cstr(getdate())
		before = self._today_count(self._summary()["peers_per_day"], today)
		fixtures.make_peer("wg8", peer_name="carol")
		after = self._today_count(self._summary()["peers_per_day"], today)
		self.assertEqual(after, before + 1)

	@staticmethod
	def _today_count(rows, today):
		return next((row["count"] for row in rows if row["day"] == today), 0)

	def test_admin_gated_for_non_admin(self):
		frappe.set_user("viewer@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			dashboard.dashboard_summary()

	def test_payload_carries_no_key_material(self):
		fixtures.make_peer("wg8", peer_name="dave")
		payload = frappe.as_json(self._summary())
		for secret in ("private_key", "preshared_key", "server_private_key"):
			self.assertNotIn(secret, payload)
