# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.tests import IntegrationTestCase

from vpn_management import firewall
from vpn_management.vpn_management.tests import fixtures


class TestFirewallRules(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")

	def test_seed_creates_the_four_default_rules(self):
		self.assertEqual(
			[rule.rule_type for rule in self.server.firewall_rules],
			["FORWARD_IN", "FORWARD_OUT", "MASQUERADE", "REDIRECT"],
		)

	def test_only_the_redirect_is_persistent(self):
		teardown = {rule.rule_type: rule.teardown_on_down for rule in self.server.firewall_rules}
		self.assertFalse(teardown["REDIRECT"])
		self.assertTrue(all(teardown[t] for t in ("FORWARD_IN", "FORWARD_OUT", "MASQUERADE")))

	def test_seed_is_idempotent_on_a_server_with_rules(self):
		# A server already carrying rules is left untouched (no duplicate seeding).
		firewall.seed_rules(self.server)
		self.assertEqual(len(self.server.firewall_rules), 4)

	def test_render_postup_is_idempotent_and_interpolates_context(self):
		commands = firewall.render_postup(self.server)
		self.assertEqual(len(commands), 4)
		# Each add is guarded -C … || -A … so a re-run never stacks a host rule.
		self.assertTrue(all(" -C " in c and " || iptables " in c and " -A " in c for c in commands))
		forward_in = next(c for c in commands if "FORWARD -i wg8" in c)
		self.assertEqual(
			forward_in,
			"iptables -t filter -C FORWARD -i wg8 -j ACCEPT "
			"|| iptables -t filter -A FORWARD -i wg8 -j ACCEPT",
		)
		self.assertTrue(any("-A POSTROUTING -o eth0 -j MASQUERADE" in c for c in commands))
		redirect = next(command for command in commands if "REDIRECT" in command)
		self.assertIn("-m multiport --dport 333,666,999,3333,4444", redirect)
		self.assertIn("--to-ports 44556", redirect)

	def test_render_postdown_skips_the_persistent_redirect(self):
		commands = firewall.render_postdown(self.server)
		self.assertEqual(len(commands), 3)
		self.assertTrue(all(" -D " in command for command in commands))
		self.assertFalse(any("REDIRECT" in command for command in commands))

	def test_disabled_rule_is_not_rendered(self):
		self.server.firewall_rules[0].enabled = 0
		self.assertEqual(len(firewall.render_postup(self.server)), 3)
