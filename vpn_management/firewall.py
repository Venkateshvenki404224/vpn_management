# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Firewall rules as data: seed defaults, render PostUp/PostDown.

A server's ``firewall_rules`` are seeded from these templates when it is first
created and rendered into the ``[Interface]`` ``PostUp``/``PostDown`` at reconcile
time. The ``spec`` carries placeholders (``{iface}``/``{egress}``/``{ports}`` …)
so the same template tracks a server's current egress/address and the settings'
ports. wg-quick runs PostUp only on bring-up; ``wg syncconf`` strips it, so the
never-torn-down REDIRECT cannot stack.
"""

import frappe
from frappe.utils import cint

SETTINGS = "VPN Settings"
DEFAULT_PORTS = "333,666,999,3333,4444"
DEFAULT_REDIRECT_PORT = 44556

# rule_type, ip_table, chain, spec (placeholder template), teardown_on_down.
# Four PostUp rules; only three are torn down — the PREROUTING REDIRECT is
# deliberately persistent (teardown_on_down=0) so it never flaps.
FIREWALL_TEMPLATES = (
	("FORWARD_IN", "filter", "FORWARD", "-i {iface} -j ACCEPT", 1),
	("FORWARD_OUT", "filter", "FORWARD", "-o {iface} -j ACCEPT", 1),
	("MASQUERADE", "nat", "POSTROUTING", "-o {egress} -j MASQUERADE", 1),
	(
		"REDIRECT",
		"nat",
		"PREROUTING",
		"-p udp -m multiport --dport {ports} -j REDIRECT --to-ports {redirect_port}",
		0,
	),
)


def seed_rules(server):
	"""Append the default firewall rules to a server that has none yet."""
	if server.get("firewall_rules"):
		return
	for rule_type, ip_table, chain, spec, teardown in FIREWALL_TEMPLATES:
		server.append(
			"firewall_rules",
			{
				"rule_type": rule_type,
				"ip_table": ip_table,
				"chain": chain,
				"spec": spec,
				"teardown_on_down": teardown,
				"enabled": 1,
			},
		)


def render_postup(server):
	"""Idempotent add-commands for every enabled rule (run on bring-up).

	A bring-up can re-run PostUp into the *host* iptables (the agent is
	host-networked) when a prior interface went down without a clean teardown —
	e.g. the never-torn-down REDIRECT survives. Each add is therefore guarded with
	``-C … || -A …`` so re-running never stacks a duplicate rule.
	"""
	context = _context(server)
	return [_idempotent_add(rule, context) for rule in _enabled_rules(server)]


def render_postdown(server):
	"""iptables delete-commands for the enabled rules that tear down on down."""
	context = _context(server)
	return [_command(rule, "-D", context) for rule in _enabled_rules(server) if rule.teardown_on_down]


def _enabled_rules(server):
	return [rule for rule in server.firewall_rules if rule.enabled]


def _idempotent_add(rule, context):
	return f"{_command(rule, '-C', context)} || {_command(rule, '-A', context)}"


def _command(rule, action, context):
	table = rule.ip_table or "filter"
	body = rule.spec.format(**context)
	return f"iptables -t {table} {action} {rule.chain} {body}"


def _context(server):
	settings = frappe.db.get_singles_dict(SETTINGS)
	return {
		"iface": server.interface_name,
		"egress": server.egress_interface,
		"address": _ip_only(server.address_cidr),
		"ports": _setting(settings, "multiport_redirect_ports", DEFAULT_PORTS),
		"redirect_port": cint(_setting(settings, "redirect_target_port", DEFAULT_REDIRECT_PORT)),
	}


def _setting(settings, field, default):
	value = settings.get(field)
	return default if value in (None, "") else value


def _ip_only(address_cidr):
	return (address_cidr or "").split("/")[0]
