# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""after_install seeding and the loud vpn_endpoint_host gate."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import install

# Throwaway interface so this never touches the host's real wg0; test rows are
# rolled back (uncommitted), so the live scheduler never sees them.
INTERFACE = "wg7"


class TestAfterInstall(IntegrationTestCase):
	def setUp(self):
		frappe.conf["vpn_default_interface"] = INTERFACE
		frappe.conf["vpn_endpoint_host"] = "vpn.example.test"
		self._cleanup()

	def tearDown(self):
		self._cleanup()
		frappe.conf.pop("vpn_default_interface", None)
		frappe.conf.pop("vpn_endpoint_host", None)

	def _cleanup(self):
		frappe.db.delete("IP Allocation", {"server": INTERFACE})
		frappe.db.delete("Network Pool", {"server": INTERFACE})
		frappe.db.delete("WireGuard Server", {"interface_name": INTERFACE})

	def test_seeds_roles_settings_server_and_pool(self):
		with patch("frappe.enqueue"), patch("vpn_management.privileged.call", return_value={"ok": True}):
			install.after_install()
		for role, _ in install.ROLE_SPECS:
			self.assertTrue(frappe.db.exists("Role", role))
		self.assertTrue(frappe.db.exists("WireGuard Server", INTERFACE))
		self.assertTrue(frappe.db.exists("Network Pool", f"pool-{INTERFACE}"))
		self.assertEqual(frappe.db.get_single_value("VPN Settings", "vpn_endpoint_host"), "vpn.example.test")

	def test_roles_carry_expected_desk_access(self):
		with patch("frappe.enqueue"), patch("vpn_management.privileged.call", return_value={"ok": True}):
			install.after_install()
		self.assertEqual(frappe.db.get_value("Role", "VPN Admin", "desk_access"), 1)
		self.assertEqual(frappe.db.get_value("Role", "VPN User", "desk_access"), 0)

	def test_fails_loudly_when_endpoint_host_unset(self):
		frappe.conf.pop("vpn_endpoint_host", None)
		with patch("vpn_management.install._should_throw", return_value=True):
			with self.assertRaises(frappe.ValidationError):
				install._require_endpoint_host()
