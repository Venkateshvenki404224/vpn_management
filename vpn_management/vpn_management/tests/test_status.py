# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import shutil
import tempfile
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from vpn_management import audit, tasks
from vpn_management.vpn_management.tests import fixtures


class TestPollStatus(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		frappe.db.set_value("WireGuard Server", "wg8", "interface_up", 1)
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		self.peer = fixtures.make_peer("wg8")

	def _dump(self, handshake_ts, rx=1000, tx=2000, endpoint="1.2.3.4:51820"):
		# wg show <iface> dump: an interface line then one tab-separated peer line.
		interface_line = "PRIVKEY\tPUBKEY\t44556\toff"
		peer_line = "\t".join(
			[
				self.peer.public_key,
				"(none)",
				endpoint,
				f"{self.peer.assigned_ip}/32",
				str(handshake_ts),
				str(rx),
				str(tx),
				"25",
			]
		)
		return f"{interface_line}\n{peer_line}\n"

	def _poll(self, dump):
		with patch("vpn_management.privileged.call", return_value={"ok": True, "stdout": dump}):
			tasks.poll_status()

	def test_fresh_handshake_marks_active_and_records_transfer(self):
		self._poll(self._dump(int(time.time()) - 10, rx=4096, tx=8192))
		peer = frappe.get_doc("VPN Peer", self.peer.name)
		self.assertEqual(peer.status, "Active")
		self.assertEqual(peer.rx_bytes, 4096)
		self.assertEqual(peer.tx_bytes, 8192)
		self.assertTrue(peer.last_handshake)
		self.assertEqual(peer.endpoint, "1.2.3.4:51820")

	def test_last_handshake_stored_in_system_timezone(self):
		import datetime

		from frappe.utils import convert_utc_to_system_timezone, get_datetime

		epoch = int(time.time()) - 30
		self._poll(self._dump(epoch))
		stored = get_datetime(frappe.db.get_value("VPN Peer", self.peer.name, "last_handshake"))
		utc = datetime.datetime.fromtimestamp(epoch, datetime.UTC).replace(tzinfo=None)
		expected = convert_utc_to_system_timezone(utc).replace(tzinfo=None)
		self.assertEqual(stored.replace(microsecond=0), expected.replace(microsecond=0))

	def test_records_large_byte_counters_without_overflow(self):
		# Long Int peer counters must survive past the signed-Int(11) ceiling (~2.1e9).
		huge = 9_000_000_000
		self._poll(self._dump(int(time.time()) - 5, rx=huge, tx=huge))
		self.assertEqual(frappe.db.get_value("VPN Peer", self.peer.name, "rx_bytes"), huge)

	def test_idle_peer_flips_to_stale(self):
		self._poll(self._dump(int(time.time()) - 3600))
		self.assertEqual(frappe.db.get_value("VPN Peer", self.peer.name, "status"), "Stale")

	def test_never_handshaked_peer_is_stale(self):
		self._poll(self._dump(0))
		self.assertEqual(frappe.db.get_value("VPN Peer", self.peer.name, "status"), "Stale")

	def test_writes_a_status_poll_audit_row(self):
		self._poll(self._dump(int(time.time())))
		rows = frappe.get_all(
			"VPN Audit Log",
			filters={"action": "status_poll", "target": "wg8"},
			fields=["result", "actor"],
		)
		self.assertTrue(rows)
		self.assertEqual(rows[0].result, "success")
		self.assertEqual(rows[0].actor, "Administrator")

	def test_agent_failure_audits_failure_without_crashing(self):
		with patch("vpn_management.privileged.call", return_value={"ok": False, "stderr": "no device"}):
			tasks.poll_status()
		rows = frappe.get_all("VPN Audit Log", filters={"action": "status_poll", "result": "failure"})
		self.assertTrue(rows)


class TestReconcileAll(IntegrationTestCase):
	def setUp(self):
		self.render_dir = tempfile.mkdtemp()
		frappe.db.set_single_value("VPN Settings", "wg_dir", self.render_dir)
		self.server = fixtures.ensure_server("wg8")

	def tearDown(self):
		shutil.rmtree(self.render_dir, ignore_errors=True)

	def test_self_heals_after_restart_by_branching_back_to_up(self):
		with patch("vpn_management.privileged.call", return_value={"ok": True}):
			tasks.reconcile_interface("wg8")
		self.assertTrue(frappe.db.get_value("WireGuard Server", "wg8", "interface_up"))

		# Restart: the DB still reads interface_up=1 but the kernel iface is gone.
		calls = []

		def fake_call(verb, args, *rest, **kwargs):
			calls.append((verb, tuple(args)))
			if verb == "show" and list(args) == ["wg8"]:
				return {"ok": False, "stderr": "Unable to access interface: No such device"}
			return {"ok": True}

		with patch("vpn_management.privileged.call", side_effect=fake_call):
			tasks.reconcile_all()

		self.assertIn(("show", ("wg8",)), calls)  # liveness probe detected the drift
		self.assertIn(("up", ("wg8",)), calls)  # re-converged with a full bring-up (PostUp)
		self.assertTrue(frappe.db.get_value("WireGuard Server", "wg8", "interface_up"))

	def test_skips_bring_up_when_egress_is_missing(self):
		frappe.db.set_value("WireGuard Server", "wg8", "egress_interface", "")
		with patch("vpn_management.privileged.call") as call:
			tasks.reconcile_interface("wg8")
		call.assert_not_called()
		rows = frappe.get_all(
			"VPN Audit Log", filters={"action": "reconcile", "target": "wg8", "result": "skipped"}
		)
		self.assertTrue(rows)


class TestAuditLogGuard(IntegrationTestCase):
	def _make_row(self):
		audit.record("reconcile", "wg8", "success", detail="x")
		return frappe.get_all("VPN Audit Log", filters={"target": "wg8"}, limit=1)[0].name

	def test_administrator_can_delete(self):
		name = self._make_row()
		frappe.delete_doc("VPN Audit Log", name)
		self.assertFalse(frappe.db.exists("VPN Audit Log", name))

	def test_non_administrator_cannot_delete(self):
		name = self._make_row()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				frappe.delete_doc("VPN Audit Log", name, ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

	def test_keys_are_redacted_in_detail(self):
		key = "QFX5K3a1b2c3d4e5f6g7h8i9j0klmnopqrstuvwx1y2="
		self.assertNotIn(key, audit.redact(f"PrivateKey = {key}"))
		self.assertIn("***", audit.redact(f"PrivateKey = {key}"))
