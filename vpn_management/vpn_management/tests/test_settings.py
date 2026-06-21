# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""VPN Settings API: admin-gated, safe fields round-trip, the sync token never leaks."""

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import api
from vpn_management.vpn_management.tests import fixtures

SECRET_MIRROR = "this-should-never-be-returned"


class TestSettingsApi(IntegrationTestCase):
	def setUp(self):
		fixtures.ensure_user("settings-user@vpn.test", ["VPN User"])
		# Seed the display-mirror with a recognisable value so a leak would be obvious.
		frappe.db.set_single_value("VPN Settings", "sync_token", SECRET_MIRROR)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_get_returns_safe_fields_only(self):
		view = api.get_vpn_settings()
		self.assertEqual(set(view.keys()), set(api.SAFE_SETTINGS_FIELDS))
		self.assertNotIn("sync_token", view)

	def test_upsert_round_trips_safe_fields(self):
		api.upsert_vpn_settings(default_keepalive=42, dns_servers="1.1.1.1", status_poll_interval_min=9)
		view = api.get_vpn_settings()
		self.assertEqual(view["default_keepalive"], 42)
		self.assertEqual(view["dns_servers"], "1.1.1.1")
		self.assertEqual(view["status_poll_interval_min"], 9)

	def test_switch_toggled_off_persists(self):
		# A Switch turned off sends 0 (not None); it must overwrite a stored 1.
		api.upsert_vpn_settings(sync_enabled=1)
		self.assertEqual(api.get_vpn_settings()["sync_enabled"], 1)
		api.upsert_vpn_settings(sync_enabled=0)
		self.assertEqual(api.get_vpn_settings()["sync_enabled"], 0)

	def test_response_never_leaks_the_sync_token(self):
		# The secret mirror is set; neither read nor write may echo it back.
		read = api.get_vpn_settings()
		written = api.upsert_vpn_settings(default_keepalive=25)
		for view in (read, written):
			self.assertNotIn("sync_token", view)
			self.assertNotIn(SECRET_MIRROR, frappe.as_json(view))

	def test_upsert_does_not_write_the_sync_token(self):
		# Even after a write the mirror is untouched — it is not an accepted field.
		api.upsert_vpn_settings(default_keepalive=30)
		self.assertEqual(frappe.db.get_single_value("VPN Settings", "sync_token"), SECRET_MIRROR)

	def test_non_admin_cannot_read_settings(self):
		frappe.set_user("settings-user@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			api.get_vpn_settings()

	def test_non_admin_cannot_upsert_settings(self):
		frappe.set_user("settings-user@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			api.upsert_vpn_settings(default_keepalive=99)
