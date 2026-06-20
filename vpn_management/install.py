# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Install-time hooks for vpn_management.

The only thing phase 1 does at install is a health gate: prove the wg-agent
sidecar is reachable over its socket. If it is not, fail loudly so the operator
brings the sidecar up first (via ``deploy/install.sh``) rather than landing a
control plane that can never touch the kernel.
"""

import frappe

from vpn_management import privileged
from vpn_management.privileged import VpnAgentError


def after_install():
	_health_gate_agent_socket()


def _health_gate_agent_socket():
	try:
		privileged.call("show", [])
	except VpnAgentError as error:
		frappe.throw(
			frappe._(
				"wg-agent is unreachable ({0}). Bring the sidecar up first — run "
				"deploy/install.sh from the bench root instead of a bare install-app."
			).format(error)
		)
