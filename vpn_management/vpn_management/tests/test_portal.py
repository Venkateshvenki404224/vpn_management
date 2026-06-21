# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""SPA shell boot: guest redirect, session/CSRF payload, endpoint-ready flag.

The page no longer renders peers (the Vue app fetches those over the owner-scoped
API); these tests pin the thin server contract the SPA boots from.
"""

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management.vpn_management.tests import fixtures
from vpn_management.www.vpn import index as portal


class TestVpnSpaBoot(IntegrationTestCase):
	def setUp(self):
		fixtures.ensure_user("alice@vpn.test", ["VPN User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.flags.redirect_location = None

	def test_guest_is_redirected_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			portal.get_context(frappe._dict())
		location = frappe.local.flags.redirect_location
		self.assertIn("/login", location)
		self.assertIn("redirect-to", location)

	def test_boot_carries_session_and_csrf(self):
		frappe.set_user("alice@vpn.test")
		boot = portal.get_context(frappe._dict()).boot
		self.assertEqual(boot["session_user"], "alice@vpn.test")
		self.assertIsInstance(boot["csrf_token"], str)
		self.assertTrue(boot["csrf_token"])

	def test_boot_endpoint_ready_is_a_bool(self):
		frappe.set_user("alice@vpn.test")
		boot = portal.get_context(frappe._dict()).boot
		self.assertIn("endpoint_ready", boot)
		self.assertIsInstance(boot["endpoint_ready"], bool)

	def test_endpoint_ready_true_when_host_configured(self):
		frappe.db.set_single_value("VPN Settings", "vpn_endpoint_host", "vpn.example.com")
		self.assertTrue(portal._endpoint_ready())
