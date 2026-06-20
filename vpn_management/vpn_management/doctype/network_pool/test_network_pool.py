# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management.vpn_management.tests import fixtures


def _new_pool(**overrides):
	values = {
		"doctype": "Network Pool",
		"pool_name": "pool-wg8",
		"server": "wg8",
		"cidr": "10.66.0.0/29",
		"gateway_ip": "10.66.0.1",
	}
	values.update(overrides)
	return frappe.get_doc(values)


class TestNetworkPool(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")

	@patch("frappe.enqueue")
	def test_rejects_invalid_cidr(self, _enqueue):
		self.assertRaises(frappe.ValidationError, _new_pool(cidr="not-a-cidr").insert)

	@patch("frappe.enqueue")
	def test_rejects_gateway_outside_cidr(self, _enqueue):
		self.assertRaises(frappe.ValidationError, _new_pool(gateway_ip="10.99.0.1").insert)

	@patch("frappe.enqueue")
	def test_save_enqueues_deduplicated_materialize(self, enqueue):
		_new_pool().insert()
		enqueue.assert_called_with(
			"vpn_management.tasks.materialize_pool",
			queue="long",
			enqueue_after_commit=True,
			job_id="materialize-pool-wg8",
			deduplicate=True,
			pool_name="pool-wg8",
		)

	@patch("frappe.enqueue")
	def test_rejects_non_ip_gateway(self, _enqueue):
		self.assertRaises(frappe.ValidationError, _new_pool(gateway_ip="not-an-ip").insert)

	@patch("frappe.enqueue")
	def test_rejects_inverted_reserved_range(self, _enqueue):
		pool = _new_pool(reserved_ranges=[{"start_ip": "10.66.0.5", "end_ip": "10.66.0.3"}])
		self.assertRaises(frappe.ValidationError, pool.insert)

	@patch("frappe.enqueue")
	def test_rejects_reserved_range_outside_cidr(self, _enqueue):
		pool = _new_pool(reserved_ranges=[{"start_ip": "10.66.0.3", "end_ip": "10.99.0.3"}])
		self.assertRaises(frappe.ValidationError, pool.insert)

	@patch("frappe.enqueue")
	def test_blocks_cidr_change_after_materialize(self, _enqueue):
		from vpn_management import allocation

		pool = _new_pool().insert()
		allocation.materialize(pool.name)
		pool.cidr = "10.55.0.0/29"
		self.assertRaises(frappe.ValidationError, pool.save)
