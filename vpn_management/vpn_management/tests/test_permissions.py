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


class TestVpnUserIsolationLayers(IntegrationTestCase):
	"""The if_owner read perm (layer 2) and has_website_permission (layer 4).

	These back the SPA's owner-scoped reads the same way they backed the deleted
	Jinja portal, so the coverage moves here rather than disappearing with it.
	"""

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

	def test_vpn_user_sees_own_admin_provisioned_peer(self):
		# Peers are admin-provisioned (the doc's creator is Administrator), so list_peers
		# must scope by owner_user, not the creator — otherwise an `if_owner` read perm
		# would hide every peer from the very user who owns it (the SPA "My Peers" bug).
		frappe.set_user("alice@vpn.test")
		names = {peer["name"] for peer in api.list_peers()}
		self.assertIn(self.alice_peer.name, names)
		self.assertNotIn(self.bob_peer.name, names)

	def test_website_permission_enforces_ownership(self):
		self.assertTrue(permissions.has_website_permission(self.alice_peer, user="alice@vpn.test"))
		self.assertFalse(permissions.has_website_permission(self.bob_peer, user="alice@vpn.test"))
		self.assertTrue(permissions.has_website_permission(self.bob_peer, user="Administrator"))

	def test_permission_engine_denies_cross_user_read(self):
		# Layers 2+3: the role engine (if_owner + permission_query_conditions + has_permission)
		# denies a VPN User any peer that is not their own. (if_owner keys off the doc's
		# `owner`/creator, so the positive read path is exercised via list scoping, not here.)
		self.assertFalse(
			frappe.has_permission("VPN Peer", "read", doc=self.bob_peer.name, user="alice@vpn.test")
		)


def _pubkey():
	return crypto.generate_keypair()[1]
