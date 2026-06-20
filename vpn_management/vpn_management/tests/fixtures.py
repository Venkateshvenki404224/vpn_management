# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Shared builders for the Phase 2 integration tests.

They patch ``frappe.enqueue`` so inserting a fixture never schedules a real
reconcile, and they materialize pools synchronously so a peer can allocate.
"""

from unittest.mock import patch

import frappe

from vpn_management import allocation


def ensure_server(interface_name="wg8"):
	"""Return a freshly inserted WireGuard Server, clearing any prior fixtures."""
	frappe.db.delete("VPN Peer", {"server": interface_name})
	frappe.db.delete("IP Allocation", {"server": interface_name})
	frappe.db.delete("Network Pool", {"server": interface_name})
	frappe.db.delete("WireGuard Server", {"interface_name": interface_name})
	with patch("frappe.enqueue"):
		return frappe.get_doc(
			{"doctype": "WireGuard Server", "interface_name": interface_name, "environment": "dev"}
		).insert()


def seed_pool(server, cidr="10.66.0.0/29", gateway="10.66.0.1", reserved_ranges=None):
	"""Insert a Network Pool for ``server`` and materialize it synchronously."""
	with patch("frappe.enqueue"):
		pool = frappe.get_doc(
			{
				"doctype": "Network Pool",
				"pool_name": f"pool-{server}",
				"server": server,
				"cidr": cidr,
				"gateway_ip": gateway,
				"reserved_ranges": reserved_ranges or [],
			}
		).insert()
	allocation.materialize(pool.name)
	return pool


def make_peer(server, **overrides):
	"""Insert a VPN Peer on ``server`` (keygen + allocation happen on insert)."""
	values = {"doctype": "VPN Peer", "peer_name": "alice", "server": server}
	values.update(overrides)
	with patch("frappe.enqueue"):
		return frappe.get_doc(values).insert()
