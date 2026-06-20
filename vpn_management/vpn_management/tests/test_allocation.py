# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import allocation
from vpn_management.vpn_management.tests import fixtures


class TestAllocation(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		self.pool = fixtures.seed_pool(self.server.name, cidr="10.66.0.0/29", gateway="10.66.0.1")

	def test_materialize_creates_host_rows_with_gateway_reserved(self):
		rows = frappe.get_all(
			"IP Allocation", filters={"server": "wg8"}, fields=["ip_address", "allocated", "reserved"]
		)
		by_ip = {row.ip_address: row for row in rows}
		self.assertEqual(len(rows), 6)  # .1 .. .6
		self.assertTrue(by_ip["10.66.0.1"].reserved)
		self.assertFalse(by_ip["10.66.0.2"].reserved)
		self.assertTrue(all(not row.allocated for row in rows))
		self.assertEqual(frappe.db.get_value("Network Pool", self.pool.name, "total_addresses"), 6)

	def test_materialize_is_idempotent_and_keeps_flags(self):
		frappe.db.set_value("IP Allocation", "wg8-10.66.0.2", "allocated", 1)
		allocation.materialize(self.pool.name)
		self.assertEqual(frappe.db.count("IP Allocation", {"server": "wg8"}), 6)
		self.assertTrue(frappe.db.get_value("IP Allocation", "wg8-10.66.0.2", "allocated"))

	def test_reserved_range_marks_addresses(self):
		server = fixtures.ensure_server("wg7")
		fixtures.seed_pool(
			server.name,
			cidr="10.77.0.0/29",
			gateway="10.77.0.1",
			reserved_ranges=[{"start_ip": "10.77.0.3", "end_ip": "10.77.0.4", "reason": "infra"}],
		)
		reserved = frappe.db.get_value("IP Allocation", "wg7-10.77.0.3", "reserved")
		free = frappe.db.get_value("IP Allocation", "wg7-10.77.0.5", "reserved")
		self.assertTrue(reserved)
		self.assertFalse(free)

	def test_claim_picks_lowest_free_skipping_reserved(self):
		claimed = allocation.claim("wg8", "PEER-T1")
		self.assertEqual(claimed.ip_address, "10.66.0.2")
		row = frappe.db.get_value("IP Allocation", claimed.name, ["allocated", "peer"], as_dict=True)
		self.assertTrue(row.allocated)
		self.assertEqual(row.peer, "PEER-T1")

	def test_claim_skips_already_allocated(self):
		first = allocation.claim("wg8", "PEER-T1")
		second = allocation.claim("wg8", "PEER-T2")
		self.assertEqual(first.ip_address, "10.66.0.2")
		self.assertEqual(second.ip_address, "10.66.0.3")

	def test_claim_throws_on_exhaustion(self):
		for index in range(5):  # .2 .. .6 are the five free addresses
			allocation.claim("wg8", f"PEER-{index}")
		self.assertRaises(frappe.ValidationError, allocation.claim, "wg8", "PEER-X")

	def test_release_frees_without_deleting_row(self):
		claimed = allocation.claim("wg8", "PEER-T1")
		allocation.release(claimed.name)
		row = frappe.db.get_value("IP Allocation", claimed.name, ["allocated", "peer"], as_dict=True)
		self.assertFalse(row.allocated)
		self.assertIsNone(row.peer)
		self.assertTrue(frappe.db.exists("IP Allocation", claimed.name))

	def test_rematerialize_reconciles_reserved_on_free_rows(self):
		self.assertFalse(frappe.db.get_value("IP Allocation", "wg8-10.66.0.3", "reserved"))
		pool = frappe.get_doc("Network Pool", self.pool.name)
		pool.append("reserved_ranges", {"start_ip": "10.66.0.3", "end_ip": "10.66.0.3", "reason": "infra"})
		with patch("frappe.enqueue"):
			pool.save()
		allocation.materialize(self.pool.name)
		self.assertTrue(frappe.db.get_value("IP Allocation", "wg8-10.66.0.3", "reserved"))

	def test_claim_on_unmaterialized_pool_reports_clearly(self):
		frappe.db.delete("IP Allocation", {"server": "wg8"})
		with self.assertRaises(frappe.ValidationError) as caught:
			allocation.claim("wg8", "PEER-X")
		self.assertIn("materialized", str(caught.exception))
