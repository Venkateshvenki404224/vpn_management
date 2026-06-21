# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Self-service portal: owner-scoped listing, guest rejection, empty state."""

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import crypto, permissions
from vpn_management.vpn_management.tests import fixtures
from vpn_management.www import vpn as portal


class TestVpnPortal(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.ensure_user("alice@vpn.test", ["VPN User"])
		fixtures.ensure_user("bob@vpn.test", ["VPN User"])
		self.alice_peer = fixtures.make_peer(
			"wg8", peer_name="alice-peer", owner_user="alice@vpn.test", public_key=_pubkey()
		)
		self.bob_peer = fixtures.make_peer(
			"wg8", peer_name="bob-peer", owner_user="bob@vpn.test", public_key=_pubkey()
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guest_is_rejected(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			portal.get_context(frappe._dict())

	def test_lists_only_own_peers(self):
		frappe.set_user("alice@vpn.test")
		context = portal.get_context(frappe._dict())
		names = {peer["name"] for peer in context.peers}
		self.assertIn(self.alice_peer.name, names)
		self.assertNotIn(self.bob_peer.name, names)

	def test_peer_rows_carry_links_and_no_key_material(self):
		frappe.set_user("alice@vpn.test")
		context = portal.get_context(frappe._dict())
		row = context.peers[0]
		self.assertIn("my_config_download", row["conf_url"])
		self.assertIn("my_config_qr", row["qr_url"])
		# Exact safe allowlist: any extra field (e.g. a key) leaking into the row fails here.
		self.assertEqual(
			set(row.keys()),
			{"name", "peer_name", "server", "assigned_ip", "status", "last_handshake", "conf_url", "qr_url"},
		)

	def test_disabled_peer_is_excluded(self):
		off = fixtures.make_peer(
			"wg8", peer_name="alice-off", owner_user="alice@vpn.test", enabled=0, public_key=_pubkey()
		)
		frappe.set_user("alice@vpn.test")
		names = {peer["name"] for peer in portal.get_context(frappe._dict()).peers}
		self.assertIn(self.alice_peer.name, names)
		self.assertNotIn(off.name, names)

	def test_website_permission_enforces_ownership(self):
		# Layer 4: has_website_permission gates the website doc path on owner_user.
		self.assertTrue(permissions.has_website_permission(self.alice_peer, user="alice@vpn.test"))
		self.assertFalse(permissions.has_website_permission(self.bob_peer, user="alice@vpn.test"))
		self.assertTrue(permissions.has_website_permission(self.bob_peer, user="Administrator"))

	def test_permission_engine_denies_cross_user_read(self):
		# Layers 2+3: the role engine (if_owner + permission_query_conditions + has_permission)
		# denies a VPN User any peer that is not their own.
		self.assertFalse(
			frappe.has_permission("VPN Peer", "read", doc=self.bob_peer.name, user="alice@vpn.test")
		)

	def test_peerless_user_sees_empty_state(self):
		fixtures.ensure_user("nobody@vpn.test", ["VPN User"])
		frappe.set_user("nobody@vpn.test")
		context = portal.get_context(frappe._dict())
		self.assertEqual(context.peers, [])


def _pubkey():
	return crypto.generate_keypair()[1]
