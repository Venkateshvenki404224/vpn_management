# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""REST surface: CRUD honors roles and no response ever carries key material."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import get_decrypted_password

from vpn_management import api, crypto
from vpn_management.vpn_management.tests import fixtures


class TestPeerApi(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.ensure_user("machine@vpn.test", ["VPN API"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_api_caller_create_allocates_ip_and_hides_keys(self):
		frappe.set_user("machine@vpn.test")
		with patch("frappe.enqueue"):
			result = api.create_peer(peer_name="m1", server="wg8", public_key=crypto.generate_keypair()[1])
		self.assertNotIn("private_key", result)
		self.assertNotIn("preshared_key", result)
		self.assertTrue(result["assigned_ip"])
		self.assertEqual(result["owner_user"], "machine@vpn.test")

	def test_api_caller_must_supply_public_key(self):
		frappe.set_user("machine@vpn.test")
		with self.assertRaises(frappe.ValidationError):
			api.create_peer(peer_name="m2", server="wg8")

	def test_admin_keygen_stores_private_key_but_response_hides_it(self):
		with patch("frappe.enqueue"):
			result = api.create_peer(peer_name="adminpeer", server="wg8")
		self.assertNotIn("private_key", result)
		stored = get_decrypted_password("VPN Peer", result["name"], "private_key", raise_exception=False)
		self.assertTrue(stored)

	def test_revoke_frees_ip_and_marks_revoked(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="r1", server="wg8", public_key=crypto.generate_keypair()[1])
			revoked = api.revoke_peer(created["name"])
		self.assertEqual(revoked["status"], "Revoked")
		self.assertFalse(revoked["enabled"])
		self.assertFalse(frappe.db.get_value("VPN Peer", created["name"], "assigned_ip"))

	def test_delete_peer_removes_row(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="d1", server="wg8", public_key=crypto.generate_keypair()[1])
			api.delete_peer(created["name"])
		self.assertFalse(frappe.db.exists("VPN Peer", created["name"]))

	def test_regenerate_keys_rotates_public_key_without_leaking_private(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="g1", server="wg8")
			before = created["public_key"]
			rotated = api.regenerate_keys(created["name"])
		self.assertNotIn("private_key", rotated)
		self.assertNotEqual(rotated["public_key"], before)

	def test_regenerate_keys_denied_for_api_caller(self):
		# Non-admins lack permlevel-1 write, so server-side keygen would desync the
		# keypair; the guard must reject them outright.
		frappe.set_user("machine@vpn.test")
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="g2", server="wg8", public_key=crypto.generate_keypair()[1])
		with self.assertRaises(frappe.PermissionError):
			api.regenerate_keys(created["name"])

	def test_interface_status_excludes_server_private_key(self):
		status = api.interface_status("wg8")
		self.assertNotIn("server_private_key", status)
		self.assertEqual(status["interface_name"], "wg8")

	def test_server_private_key_readable_only_by_vpn_admin(self):
		# The spec's "server_private_key unreadable to every role but VPN Admin" —
		# verified at the permission layer, not just the response allowlist.
		fixtures.ensure_user("vadmin@vpn.test", ["VPN Admin"])
		server = frappe.get_doc("WireGuard Server", "wg8")
		frappe.set_user("machine@vpn.test")  # VPN API
		self.assertNotIn(1, server.get_permlevel_access("read"))
		frappe.set_user("vadmin@vpn.test")  # VPN Admin
		self.assertIn(1, server.get_permlevel_access("read"))

	def test_get_peer_status_returns_live_fields(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="s1", server="wg8", public_key=crypto.generate_keypair()[1])
		status = api.get_peer_status(created["name"])
		self.assertEqual(status["name"], created["name"])
		self.assertIn("rx_bytes", status)
		self.assertNotIn("private_key", status)
