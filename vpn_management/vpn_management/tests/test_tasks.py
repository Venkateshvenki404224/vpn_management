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


class TestProvisionServer(IntegrationTestCase):
	def setUp(self):
		self.render_dir = tempfile.mkdtemp()
		frappe.db.set_single_value("VPN Settings", "wg_dir", self.render_dir)
		frappe.db.delete("WireGuard Server", {"interface_name": "wg8"})
		with patch("frappe.enqueue"):
			self.server = frappe.get_doc(
				{"doctype": "WireGuard Server", "interface_name": "wg8", "environment": "dev"}
			).insert()

	def tearDown(self):
		shutil.rmtree(self.render_dir, ignore_errors=True)

	def _conf_path(self):
		return os.path.join(self.render_dir, "wg8.conf")

	def test_brings_interface_up_and_renders_conf(self):
		replies = {("show", ()): {"ok": True, "stdout": ""}, ("up", ("wg8",)): {"ok": True}}
		with patch("vpn_management.privileged.call", side_effect=_router(replies)) as call:
			tasks.provision_server("wg8")

		self.assertIn(["up", ["wg8"]], [list(c.args) for c in call.call_args_list])
		conf = frappe.read_file(self._conf_path())
		self.assertIn("[Interface]", conf)
		self.assertIn("Address = 172.27.0.1/16", conf)
		self.assertIn("ListenPort = 44556", conf)
		self.assertEqual(stat.S_IMODE(os.stat(self._conf_path()).st_mode), 0o600)

		server = frappe.get_doc("WireGuard Server", "wg8")
		self.assertEqual(server.status, "Up")
		self.assertTrue(server.provisioned)
		self.assertTrue(server.interface_up)
		self.assertTrue(server.last_reconcile)

	def test_idempotent_when_interface_already_live(self):
		replies = {("show", ()): {"ok": True, "stdout": "wg8"}}
		with patch("vpn_management.privileged.call", side_effect=_router(replies)) as call:
			tasks.provision_server("wg8")

		verbs = [c.args[0] for c in call.call_args_list]
		self.assertNotIn("up", verbs)
		self.assertEqual(frappe.db.get_value("WireGuard Server", "wg8", "status"), "Up")

	def test_keys_unchanged_across_reprovision(self):
		before = self.server.get_password("server_private_key")
		replies = {("show", ()): {"ok": True, "stdout": "wg8"}}
		with patch("vpn_management.privileged.call", side_effect=_router(replies)):
			tasks.provision_server("wg8")
		after = frappe.get_doc("WireGuard Server", "wg8").get_password("server_private_key")
		self.assertEqual(before, after)

	def test_marks_error_without_crashing_on_socket_failure(self):
		with patch("vpn_management.privileged.call", side_effect=VpnAgentError("socket down")):
			tasks.provision_server("wg8")

		server = frappe.get_doc("WireGuard Server", "wg8")
		self.assertEqual(server.status, "Error")
		self.assertFalse(server.interface_up)


def _router(replies):
	"""Build a privileged.call stub that answers by (verb, tuple(args))."""

	def _call(verb, args, *rest, **kwargs):
		return replies[(verb, tuple(args))]

	return _call
