# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WireGuardFirewallRule(Document):
	"""One iptables rule rendered into a server's PostUp/PostDown.

	Stored as data on ``WireGuard Server.firewall_rules``: the ``spec`` holds the
	iptables match+target args (with ``{iface}``/``{egress}``/``{ports}`` …
	placeholders) and is interpolated at reconcile time. ``teardown_on_down``
	controls whether a deleting PostDown is also rendered.
	"""

	pass
