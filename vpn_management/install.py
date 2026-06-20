# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Install-time hooks for vpn_management.

The only thing phase 1 does at install is a health gate: prove the wg-agent
sidecar is reachable over its socket. If it is not, fail loudly so the operator
brings the sidecar up first (via ``deploy/install.sh``) rather than landing a
control plane that can never touch the kernel.

CI and test installs have no sidecar by design (the socket is mocked in tests),
so there the gate downgrades to a warning instead of aborting the install.
"""

import os

import frappe

from vpn_management import privileged
from vpn_management.privileged import VpnAgentError


def after_install():
	_health_gate_agent_socket()


def _health_gate_agent_socket():
	try:
		privileged.call("show", [])
	except VpnAgentError as error:
		_handle_unreachable_agent(error)


def _handle_unreachable_agent(error):
	if os.environ.get("CI") or frappe.flags.in_test:
		frappe.logger("vpn_management").warning(f"wg-agent not reachable during install: {error}")
		return
	frappe.throw(
		frappe._(
			"wg-agent is unreachable ({0}). Bring the sidecar up first — run "
			"deploy/install.sh from the bench root instead of a bare install-app."
		).format(error)
	)
