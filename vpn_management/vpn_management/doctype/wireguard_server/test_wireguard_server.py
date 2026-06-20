# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import crypto


def _new_server(**overrides):
	values = {
		"doctype": "WireGuard Server",
		"interface_name": "wg9",
		"environment": "dev",
	}
	values.update(overrides)
	return frappe.get_doc(values)


class TestWireGuardServer(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("WireGuard Server", {"interface_name": ("like", "wg9%")})

	@patch("frappe.enqueue")
	def test_keypair_generated_on_insert(self, _enqueue):
		server = _new_server().insert()
		private_key = server.get_password("server_private_key")
		self.assertTrue(private_key)
		self.assertTrue(server.server_public_key)
		self.assertEqual(crypto.public_key_for(private_key), server.server_public_key)

	@patch("frappe.enqueue")
	def test_address_cidr_computed_from_environment(self, _enqueue):
		self.assertEqual(_new_server(environment="dev").insert().address_cidr, "172.27.0.1/16")
		self.assertEqual(
			_new_server(interface_name="wg91", environment="prod").insert().address_cidr,
			"172.30.0.1/16",
		)

	@patch("frappe.enqueue")
	def test_address_cidr_is_overridable(self, _enqueue):
		server = _new_server(address_cidr="10.9.0.1/24").insert()
		self.assertEqual(server.address_cidr, "10.9.0.1/24")

	@patch("frappe.enqueue")
	def test_rejects_bad_interface_name(self, _enqueue):
		self.assertRaises(frappe.ValidationError, _new_server(interface_name="eth0").insert)

	@patch("frappe.enqueue")
	def test_rejects_out_of_range_port(self, _enqueue):
		self.assertRaises(frappe.ValidationError, _new_server(listen_port=70000).insert)

	@patch("frappe.enqueue")
	def test_save_enqueues_deduplicated_reconcile(self, enqueue):
		_new_server().insert()
		enqueue.assert_called_with(
			"vpn_management.tasks.reconcile_interface",
			queue="long",
			enqueue_after_commit=True,
			job_id="reconcile-wg9",
			deduplicate=True,
			interface_name="wg9",
		)
