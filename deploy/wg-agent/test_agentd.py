#!/usr/bin/env python3
"""Unit tests for the wg-agent security boundary.

``agentd`` is a standalone script (no ``.py`` extension) that runs in the
sidecar, so it is loaded here by path. These tests cover *only* validation —
they never shell out — and run with plain stdlib::

    python3 deploy/wg-agent/test_agentd.py
"""

import importlib.util
import os
import tempfile
import unittest
from importlib.machinery import SourceFileLoader

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_agentd():
	# `agentd` has no .py extension, so bind a source loader explicitly.
	loader = SourceFileLoader("agentd", os.path.join(_HERE, "agentd"))
	spec = importlib.util.spec_from_loader("agentd", loader)
	module = importlib.util.module_from_spec(spec)
	loader.exec_module(module)
	return module


agentd = _load_agentd()


class InterfaceValidationTests(unittest.TestCase):
	def test_accepts_canonical_interfaces(self):
		agentd.assert_iface("wg0")
		agentd.assert_iface("wg21")

	def test_rejects_injection_and_garbage(self):
		for bad in ["wg0; rm -rf /", "wg0 && reboot", "wg0/../etc", "eth0", "wg", "", "WG0", 0, None]:
			with self.assertRaises(ValueError):
				agentd.assert_iface(bad)


class ConfPathTests(unittest.TestCase):
	def test_rejects_path_outside_dir(self):
		with tempfile.TemporaryDirectory() as base:
			with self.assertRaises(ValueError):
				agentd.assert_under_dir("/etc/passwd", base)

	def test_rejects_symlink_escape(self):
		with tempfile.TemporaryDirectory() as base:
			link = os.path.join(base, "wg0.conf")
			os.symlink("/etc/passwd", link)
			with self.assertRaises(ValueError):
				agentd.assert_under_dir(link, base)


class ReadValidatedConfTests(unittest.TestCase):
	def setUp(self):
		self._original_dir = agentd.WG_DIR
		self.base = tempfile.mkdtemp()
		agentd.WG_DIR = self.base

	def tearDown(self):
		agentd.WG_DIR = self._original_dir

	def _write(self, body, mode=0o600):
		path = os.path.join(self.base, "wg0.conf")
		with open(path, "w") as handle:
			handle.write(body)
		os.chmod(path, mode)
		return path

	def test_rejects_world_readable_conf(self):
		self._write("[Interface]\nPrivateKey = AAAA\n", mode=0o644)
		with self.assertRaises(ValueError):
			agentd.read_validated_conf("wg0")

	def test_rejects_missing_conf(self):
		with self.assertRaises(OSError):
			agentd.read_validated_conf("wg0")

	def test_rejects_directive(self):
		self._write("[Interface]\nPrivateKey = AAAA\nPostUp = id\n")
		with self.assertRaises(ValueError):
			agentd.read_validated_conf("wg0")

	def test_returns_owner_only_validated_bytes(self):
		body = "[Interface]\nPrivateKey = AAAA\nAddress = 10.0.0.1/24\n"
		self._write(body)
		self.assertEqual(agentd.read_validated_conf("wg0"), body.encode("utf-8"))


class ConfSafeTests(unittest.TestCase):
	def _write(self, base, body):
		path = os.path.join(base, "wg0.conf")
		with open(path, "w") as handle:
			handle.write(body)
		os.chmod(path, 0o600)
		return path

	def test_accepts_inert_interface_conf(self):
		with tempfile.TemporaryDirectory() as base:
			path = self._write(
				base, "[Interface]\nPrivateKey = AAAA\nAddress = 10.0.0.1/24\nListenPort = 51820\n"
			)
			agentd.assert_conf_safe(path)

	def test_rejects_postup_directive(self):
		with tempfile.TemporaryDirectory() as base:
			path = self._write(base, "[Interface]\nPrivateKey = AAAA\nPostUp = bash -c 'id'\n")
			with self.assertRaises(ValueError):
				agentd.assert_conf_safe(path)

	def test_rejects_saveconfig_and_unknown_section(self):
		with tempfile.TemporaryDirectory() as base:
			for body in ["[Interface]\nSaveConfig = true\n", "[Evil]\nPrivateKey = AAAA\n"]:
				with self.assertRaises(ValueError):
					agentd.assert_conf_safe(self._write(base, body))

	def test_accepts_iptables_postup_postdown(self):
		body = (
			"[Interface]\nPrivateKey = AAAA\nAddress = 10.0.0.1/24\n"
			"PostUp = iptables -t filter -A FORWARD -i wg0 -j ACCEPT\n"
			"PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
			"PostUp = iptables -t nat -A PREROUTING -p udp -m multiport --dport 333,666,999 -j REDIRECT --to-ports 44556\n"
			"PostDown = iptables -t filter -D FORWARD -i wg0 -j ACCEPT\n"
		)
		with tempfile.TemporaryDirectory() as base:
			agentd.assert_conf_safe(self._write(base, body))

	def test_rejects_postup_with_smuggled_command(self):
		body = "[Interface]\nPrivateKey = AAAA\nPostUp = iptables -A FORWARD -j ACCEPT; rm -rf /\n"
		with tempfile.TemporaryDirectory() as base:
			with self.assertRaises(ValueError):
				agentd.assert_conf_safe(self._write(base, body))


class FirewallDirectiveTests(unittest.TestCase):
	def test_accepts_iptables_and_ip6tables(self):
		agentd._assert_firewall_directive("iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE")
		agentd._assert_firewall_directive("ip6tables -A FORWARD -i wg0 -j ACCEPT")
		# Multiple iptables commands chained with the wg-quick ';' separator.
		agentd._assert_firewall_directive(
			"iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT"
		)

	def test_accepts_idempotent_check_or_add(self):
		# The app renders check-then-add ('-C … || -A …'); '||' joins two iptables calls.
		agentd._assert_firewall_directive(
			"iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE "
			"|| iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
		)
		agentd._assert_firewall_directive(
			"iptables -t nat -C PREROUTING -p udp -m multiport --dport 333,666 -j REDIRECT --to-ports 44556 "
			"|| iptables -t nat -A PREROUTING -p udp -m multiport --dport 333,666 -j REDIRECT --to-ports 44556"
		)

	def test_rejects_dangerous_iptables_semantics(self):
		# Shell-safe but root-powerful iptables that a compromised worker must not run.
		for bad in [
			"iptables -F",
			"iptables -t nat -F",
			"iptables -X",
			"iptables -Z",
			"iptables -P INPUT ACCEPT",
			"iptables -A INPUT -j ACCEPT",
			"iptables -A OUTPUT -j ACCEPT",
			"iptables -t nat -A PREROUTING -p tcp --dport 443 -j DNAT --to-destination 1.2.3.4",
			"iptables -t mangle -A FORWARD -j ACCEPT",
			"iptables -I FORWARD -j ACCEPT",
			"iptables -A FORWARD -i wg0 -j ACCEPT; iptables -F",
		]:
			with self.assertRaises(ValueError):
				agentd._assert_firewall_directive(bad)

	def test_rejects_non_iptables_command(self):
		for bad in ["id", "bash -c id", "iptables -A FORWARD -j ACCEPT; reboot", ""]:
			with self.assertRaises(ValueError):
				agentd._assert_firewall_directive(bad)

	def test_rejects_shell_metacharacters(self):
		for bad in [
			"iptables -A FORWARD -j ACCEPT && reboot",
			"iptables -A FORWARD -j ACCEPT | sh",
			"iptables -A FORWARD $(reboot)",
			"iptables -A FORWARD `reboot`",
			"iptables -A FORWARD -j ACCEPT > /etc/passwd",
		]:
			with self.assertRaises(ValueError):
				agentd._assert_firewall_directive(bad)


class DispatchTests(unittest.TestCase):
	def setUp(self):
		self._original_run = agentd.run
		self.calls = []
		agentd.run = lambda command: self.calls.append(command) or {"ok": True}

	def tearDown(self):
		agentd.run = self._original_run

	def test_unknown_verb_rejected(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb": "destroy", "args": []}')

	def test_oversized_payload_rejected(self):
		payload = b'{"verb":"show","args":[]}' + b" " * (agentd.MAX_REQUEST + 1)
		with self.assertRaises(ValueError):
			agentd.dispatch(payload)

	def test_non_object_request_rejected(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'["show"]')

	def test_args_must_be_a_list(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb":"show","args":"wg0"}')

	def test_show_without_args_lists_interfaces(self):
		agentd.dispatch(b'{"verb":"show","args":[]}')
		self.assertEqual(self.calls, [["wg", "show", "interfaces"]])

	def test_show_interface_dump(self):
		agentd.dispatch(b'{"verb":"show","args":["wg0","dump"]}')
		self.assertEqual(self.calls, [["wg", "show", "wg0", "dump"]])

	def test_show_rejects_unknown_subcommand(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb":"show","args":["wg0","garbage"]}')
		self.assertEqual(self.calls, [])

	def test_up_rejects_bad_interface_before_running(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb":"up","args":["wg0; rm -rf /"]}')
		self.assertEqual(self.calls, [])

	def test_up_rejects_conf_with_directive_before_running(self):
		original = agentd.WG_DIR
		with tempfile.TemporaryDirectory() as base:
			agentd.WG_DIR = base
			path = os.path.join(base, "wg0.conf")
			with open(path, "w") as handle:
				handle.write("[Interface]\nPrivateKey = AAAA\nPostUp = bash -c 'id'\n")
			os.chmod(path, 0o600)
			try:
				with self.assertRaises(ValueError):
					agentd.dispatch(b'{"verb":"up","args":["wg0"]}')
				self.assertEqual(self.calls, [])
			finally:
				agentd.WG_DIR = original


class SyncconfTests(unittest.TestCase):
	def setUp(self):
		self._original_dir = agentd.WG_DIR
		self._original_stage = agentd.STAGE_DIR
		self._original_run = agentd.run_syncconf
		self.base = tempfile.mkdtemp()
		self.stage = tempfile.mkdtemp()
		agentd.WG_DIR = self.base
		agentd.STAGE_DIR = self.stage
		self.calls = []
		agentd.run_syncconf = lambda iface, path: self.calls.append((iface, path)) or {"ok": True}

	def tearDown(self):
		agentd.WG_DIR = self._original_dir
		agentd.STAGE_DIR = self._original_stage
		agentd.run_syncconf = self._original_run

	def _write_conf(self, body, mode=0o600):
		path = os.path.join(self.base, "wg0.conf")
		with open(path, "w") as handle:
			handle.write(body)
		os.chmod(path, mode)
		return path

	def test_requires_two_args(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb":"syncconf","args":["wg0"]}')
		self.assertEqual(self.calls, [])

	def test_rejects_bad_interface(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb":"syncconf","args":["wg0; reboot","/etc/wireguard/wg0.conf"]}')
		self.assertEqual(self.calls, [])

	def test_rejects_conf_outside_dir(self):
		with self.assertRaises(ValueError):
			agentd.dispatch(b'{"verb":"syncconf","args":["wg0","/etc/passwd"]}')
		self.assertEqual(self.calls, [])

	def _payload(self, path):
		return ('{"verb": "syncconf", "args": ["wg0", "%s"]}' % path).encode("utf-8")

	def test_rejects_world_readable_conf(self):
		path = self._write_conf("[Interface]\nPrivateKey = AAAA\n", mode=0o644)
		with self.assertRaises(ValueError):
			agentd.dispatch(self._payload(path))
		self.assertEqual(self.calls, [])

	def test_rejects_conf_with_directive(self):
		path = self._write_conf("[Interface]\nPrivateKey = AAAA\nPostUp = bash -c 'id'\n")
		with self.assertRaises(ValueError):
			agentd.dispatch(self._payload(path))
		self.assertEqual(self.calls, [])

	def test_validates_and_runs_against_staged_copy(self):
		path = self._write_conf("[Interface]\nPrivateKey = AAAA\nAddress = 10.0.0.1/24\n")
		reply = agentd.dispatch(self._payload(path))
		self.assertTrue(reply["ok"])
		# syncconf consumes the root-owned staged copy, not the worker's render dir.
		self.assertEqual(self.calls, [("wg0", os.path.join(self.stage, "wg0.conf"))])

	def test_rejects_conf_not_matching_interface(self):
		other = os.path.join(self.base, "wg1.conf")
		with open(other, "w") as handle:
			handle.write("[Interface]\nPrivateKey = AAAA\n")
		os.chmod(other, 0o600)
		with self.assertRaises(ValueError):
			agentd.dispatch(self._payload(other))
		self.assertEqual(self.calls, [])


class UpTests(unittest.TestCase):
	def setUp(self):
		self._original_dir = agentd.WG_DIR
		self._original_stage = agentd.STAGE_DIR
		self._original_run = agentd.run
		self.base = tempfile.mkdtemp()
		self.stage = tempfile.mkdtemp()
		agentd.WG_DIR = self.base
		agentd.STAGE_DIR = self.stage
		self.calls = []
		agentd.run = lambda command: self.calls.append(command) or {"ok": True}

	def tearDown(self):
		agentd.WG_DIR = self._original_dir
		agentd.STAGE_DIR = self._original_stage
		agentd.run = self._original_run

	def _write(self, body, mode=0o600):
		path = os.path.join(self.base, "wg0.conf")
		with open(path, "w") as handle:
			handle.write(body)
		os.chmod(path, mode)
		return path

	def test_up_runs_against_staged_validated_copy(self):
		body = "[Interface]\nPrivateKey = AAAA\nAddress = 10.0.0.1/24\n"
		self._write(body)
		reply = agentd.dispatch(b'{"verb":"up","args":["wg0"]}')
		self.assertTrue(reply["ok"])
		staged = os.path.join(self.stage, "wg0.conf")
		self.assertEqual(self.calls, [["wg-quick", "up", staged]])
		with open(staged) as handle:
			self.assertEqual(handle.read(), body)

	def test_up_applies_validated_bytes_even_if_conf_swapped_after_check(self):
		# TOCTOU regression: the worker swaps a root-directive conf in the instant
		# the allowlist check runs; the staged (applied) bytes must be the validated ones.
		benign = "[Interface]\nPrivateKey = AAAA\nAddress = 10.0.0.1/24\n"
		malicious = "[Interface]\nPrivateKey = AAAA\nPostUp = bash -c id\n"
		conf = self._write(benign)
		real = agentd._assert_conf_safe_text

		def swap_then_validate(text):
			with open(conf, "w") as handle:
				handle.write(malicious)
			os.chmod(conf, 0o600)
			real(text)

		agentd._assert_conf_safe_text = swap_then_validate
		try:
			agentd.dispatch(b'{"verb":"up","args":["wg0"]}')
		finally:
			agentd._assert_conf_safe_text = real
		with open(os.path.join(self.stage, "wg0.conf")) as handle:
			self.assertEqual(handle.read(), benign)


if __name__ == "__main__":
	unittest.main()
