# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Row-level VPN Peer scoping: non-admins see only the peers they own."""

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import api, crypto, permissions
from vpn_management.vpn_management.tests import fixtures


class TestPeerOwnerScoping(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.ensure_user("alice@vpn.test", ["VPN API"])
		fixtures.ensure_user("bob@vpn.test", ["VPN API"])
		self.alice_peer = fixtures.make_peer(
			"wg8", peer_name="alice-peer", owner_user="alice@vpn.test", public_key=_pubkey()
		)
		self.bob_peer = fixtures.make_peer(
			"wg8", peer_name="bob-peer", owner_user="bob@vpn.test", public_key=_pubkey()
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_query_conditions_scope_to_owner(self):
		condition = permissions.get_permission_query_conditions("alice@vpn.test")
		self.assertIn("owner_user", condition)
		self.assertIn("alice@vpn.test", condition)

	def test_admin_query_conditions_are_unrestricted(self):
		self.assertEqual(permissions.get_permission_query_conditions("Administrator"), "")

	def test_list_peers_returns_only_own(self):
		frappe.set_user("alice@vpn.test")
		names = {peer["name"] for peer in api.list_peers(server="wg8")}
		self.assertIn(self.alice_peer.name, names)
		self.assertNotIn(self.bob_peer.name, names)

	def test_get_other_owners_peer_is_denied(self):
		frappe.set_user("alice@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			api.get_peer(self.bob_peer.name)

	def test_owner_can_get_own_peer(self):
		frappe.set_user("alice@vpn.test")
		self.assertEqual(api.get_peer(self.alice_peer.name)["name"], self.alice_peer.name)

	def test_admin_sees_every_owners_peers(self):
		names = {peer["name"] for peer in api.list_peers(server="wg8")}
		self.assertIn(self.alice_peer.name, names)
		self.assertIn(self.bob_peer.name, names)


def _pubkey():
	return crypto.generate_keypair()[1]
