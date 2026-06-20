# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import os
import shutil
import stat
import tempfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import tasks
from vpn_management.privileged import VpnAgentError
from vpn_management.vpn_management.tests import fixtures


class TestReconcileInterface(IntegrationTestCase):
	def setUp(self):
		self.render_dir = tempfile.mkdtemp()
		frappe.db.set_single_value("VPN Settings", "wg_dir", self.render_dir)
		self.server = fixtures.ensure_server("wg8")

	def tearDown(self):
		shutil.rmtree(self.render_dir, ignore_errors=True)

	def _conf_path(self):
		return os.path.join(self.render_dir, "wg8.conf")

	def test_brings_interface_up_and_renders_conf(self):
		with patch(
			"vpn_management.privileged.call", side_effect=_router({("up", ("wg8",)): {"ok": True}})
		) as call:
			tasks.reconcile_interface("wg8")

		self.assertEqual([list(c.args) for c in call.call_args_list], [["up", ["wg8"]]])
		conf = frappe.read_file(self._conf_path())
		self.assertIn("[Interface]", conf)
		self.assertIn("Address = 172.27.0.1/16", conf)
		self.assertIn("ListenPort = 44556", conf)
		self.assertEqual(stat.S_IMODE(os.stat(self._conf_path()).st_mode), 0o600)

		server = frappe.get_doc("WireGuard Server", "wg8")
		self.assertEqual(server.status, "Up")
		self.assertTrue(server.interface_up)
		self.assertTrue(server.config_hash)
		self.assertTrue(server.last_reconcile)

	def test_syncconf_when_interface_already_up(self):
		frappe.db.set_value("WireGuard Server", "wg8", {"interface_up": 1, "config_hash": "stale"})
		replies = {("syncconf", ("wg8", self._conf_path())): {"ok": True}}
		with patch("vpn_management.privileged.call", side_effect=_router(replies)) as call:
			tasks.reconcile_interface("wg8")

		self.assertEqual([c.args[0] for c in call.call_args_list], ["syncconf"])

	def test_noop_when_config_hash_unchanged(self):
		replies = {
			("up", ("wg8",)): {"ok": True},
			("syncconf", ("wg8", self._conf_path())): {"ok": True},
		}
		with patch("vpn_management.privileged.call", side_effect=_router(replies)):
			tasks.reconcile_interface("wg8")  # first run records the hash + brings it up
		with patch("vpn_management.privileged.call", side_effect=_router(replies)) as call:
			tasks.reconcile_interface("wg8")  # second run is a pure no-op

		self.assertEqual(call.call_args_list, [])

	def test_renders_enabled_peer_and_marks_synced(self):
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		with patch("vpn_management.privileged.call", side_effect=_router({("up", ("wg8",)): {"ok": True}})):
			tasks.reconcile_interface("wg8")
		peer = fixtures.make_peer("wg8")

		replies = {("syncconf", ("wg8", self._conf_path())): {"ok": True}}
		with patch("vpn_management.privileged.call", side_effect=_router(replies)):
			tasks.reconcile_interface("wg8")

		conf = frappe.read_file(self._conf_path())
		self.assertIn("[Peer]", conf)
		self.assertIn(f"PublicKey = {peer.public_key}", conf)
		self.assertIn(f"AllowedIPs = {peer.assigned_ip}/32", conf)
		synced, status = frappe.db.get_value("VPN Peer", peer.name, ["synced_to_interface", "status"])
		self.assertTrue(synced)
		self.assertEqual(status, "Active")

	def test_keys_unchanged_across_reconcile(self):
		before = self.server.get_password("server_private_key")
		with patch("vpn_management.privileged.call", side_effect=_router({("up", ("wg8",)): {"ok": True}})):
			tasks.reconcile_interface("wg8")
		after = frappe.get_doc("WireGuard Server", "wg8").get_password("server_private_key")
		self.assertEqual(before, after)

	def test_marks_error_without_crashing_on_socket_failure(self):
		with patch("vpn_management.privileged.call", side_effect=VpnAgentError("socket down")):
			tasks.reconcile_interface("wg8")

		server = frappe.get_doc("WireGuard Server", "wg8")
		self.assertEqual(server.status, "Error")
		self.assertFalse(server.interface_up)

	def test_marks_error_when_render_fails(self):
		with patch("vpn_management.tasks._render_conf", side_effect=ValueError("render boom")):
			tasks.reconcile_interface("wg8")

		self.assertEqual(frappe.db.get_value("WireGuard Server", "wg8", "status"), "Error")


def _router(replies):
	"""Build a privileged.call stub that answers by (verb, tuple(args))."""

	def _call(verb, args, *rest, **kwargs):
		return replies[(verb, tuple(args))]

	return _call
