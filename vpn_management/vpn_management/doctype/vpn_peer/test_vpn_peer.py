# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import crypto
from vpn_management.vpn_management.tests import fixtures


class TestVPNPeer(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool(self.server.name, cidr="10.66.0.0/29", gateway="10.66.0.1")

	def test_keypair_generated_on_insert(self):
		peer = fixtures.make_peer("wg8")
		self.assertTrue(peer.public_key)
		self.assertTrue(peer.get_password("private_key"))
		self.assertEqual(crypto.public_key_for(peer.get_password("private_key")), peer.public_key)

	def test_allocates_lowest_ip_on_insert(self):
		peer = fixtures.make_peer("wg8")
		self.assertEqual(peer.assigned_ip, "10.66.0.2")
		self.assertEqual(peer.allowed_ips, "10.66.0.2/32")
		alloc = frappe.db.get_value("IP Allocation", peer.ip_allocation, ["allocated", "peer"], as_dict=True)
		self.assertTrue(alloc.allocated)
		self.assertEqual(alloc.peer, peer.name)

	def test_user_supplied_public_key_skips_keygen(self):
		_, public_key = crypto.generate_keypair()
		peer = fixtures.make_peer("wg8", public_key=public_key)
		self.assertEqual(peer.public_key, public_key)
		self.assertFalse(peer.get_password("private_key", raise_exception=False))

	def test_rejects_missing_key_when_keygen_disabled(self):
		frappe.db.set_single_value("VPN Settings", "allow_server_keygen", 0)
		try:
			self.assertRaises(frappe.ValidationError, fixtures.make_peer, "wg8")
		finally:
			frappe.db.set_single_value("VPN Settings", "allow_server_keygen", 1)

	def test_rejects_invalid_public_key(self):
		self.assertRaises(frappe.ValidationError, fixtures.make_peer, "wg8", public_key="not-valid-base64!!")

	def test_disable_frees_ip_and_keeps_row(self):
		peer = fixtures.make_peer("wg8")
		allocation_name = peer.ip_allocation
		with patch("frappe.enqueue"):
			peer.enabled = 0
			peer.save()
		peer.reload()
		self.assertFalse(peer.ip_allocation)
		self.assertEqual(peer.status, "Disabled")
		alloc = frappe.db.get_value("IP Allocation", allocation_name, ["allocated", "peer"], as_dict=True)
		self.assertFalse(alloc.allocated)
		self.assertIsNone(alloc.peer)
		self.assertTrue(frappe.db.exists("IP Allocation", allocation_name))

	def test_trash_frees_ip_and_keeps_row(self):
		peer = fixtures.make_peer("wg8")
		allocation_name = peer.ip_allocation
		with patch("frappe.enqueue"):
			peer.delete()
		alloc = frappe.db.get_value("IP Allocation", allocation_name, ["allocated", "peer"], as_dict=True)
		self.assertFalse(alloc.allocated)
		self.assertIsNone(alloc.peer)
		self.assertTrue(frappe.db.exists("IP Allocation", allocation_name))

	def test_re_enable_resets_status_and_reallocates(self):
		peer = fixtures.make_peer("wg8")
		with patch("frappe.enqueue"):
			peer.enabled = 0
			peer.save()
		self.assertEqual(peer.status, "Disabled")
		with patch("frappe.enqueue"):
			peer.enabled = 1
			peer.save()
		peer.reload()
		self.assertEqual(peer.status, "Pending")
		self.assertTrue(peer.ip_allocation)

	def test_disable_preserves_custom_allowed_ips(self):
		peer = fixtures.make_peer("wg8", allowed_ips="10.0.0.0/24")
		self.assertEqual(peer.allowed_ips, "10.0.0.0/24")
		with patch("frappe.enqueue"):
			peer.enabled = 0
			peer.save()
		peer.reload()
		self.assertEqual(peer.allowed_ips, "10.0.0.0/24")
		self.assertFalse(peer.ip_allocation)

	def test_save_enqueues_deduplicated_reconcile(self):
		with patch("frappe.enqueue") as enqueue:
			frappe.get_doc({"doctype": "VPN Peer", "peer_name": "bob", "server": "wg8"}).insert()
		enqueue.assert_called_with(
			"vpn_management.tasks.reconcile_interface",
			queue="long",
			enqueue_after_commit=True,
			job_id="reconcile-wg8",
			deduplicate=True,
			interface_name="wg8",
		)
