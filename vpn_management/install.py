# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Install-time hooks for vpn_management.

``after_install`` health-gates on the wg-agent socket (phase 1), then seeds the
control plane: the four VPN roles, ``VPN Settings``, and a default ``wg0`` server
with its ``Network Pool``. It **fails loudly** when ``vpn_endpoint_host`` is not
configured — peers cannot be handed a working client config without it.

CI and test installs have no sidecar and no site_config endpoint by design, so
there the loud gates downgrade to warnings instead of aborting the install.
"""

import ipaddress
import os

import frappe
from frappe import _

from vpn_management import privileged
from vpn_management.privileged import VpnAgentError

SETTINGS = "VPN Settings"
DEFAULT_INTERFACE = "wg0"
# role_name -> desk_access. VPN Admin runs Desk; the rest are machine/portal users.
ROLE_SPECS = (("VPN Admin", 1), ("VPN User", 0), ("VPN API", 0), ("VPN Sync", 0))


def after_install():
	_health_gate_agent_socket()
	_require_endpoint_host()
	_seed_roles()
	_seed_settings()
	_seed_default_server_and_pool()


# --- gates -----------------------------------------------------------------


def _health_gate_agent_socket():
	try:
		privileged.call("show", [])
	except VpnAgentError as error:
		_fail(
			_(
				"wg-agent is unreachable ({0}). Bring the sidecar up first — run "
				"deploy/install.sh from the bench root instead of a bare install-app."
			).format(error)
		)


def _require_endpoint_host():
	if frappe.conf.get("vpn_endpoint_host"):
		return
	_fail(
		_(
			"vpn_endpoint_host is not set. Run: bench --site <site> set-config "
			"vpn_endpoint_host <host> before installing vpn_management."
		)
	)


def _fail(message):
	"""Throw loudly on a real install; warn (don't abort) under CI / tests."""
	if _should_throw():
		frappe.throw(message)
	frappe.logger("vpn_management").warning(message)


def _should_throw():
	return not (os.environ.get("CI") or frappe.flags.in_test)


# --- seeding ---------------------------------------------------------------


def _seed_roles():
	for role_name, desk_access in ROLE_SPECS:
		_ensure_role(role_name, desk_access)


def _ensure_role(role_name, desk_access):
	if frappe.db.exists("Role", role_name):
		frappe.db.set_value("Role", role_name, "desk_access", desk_access)
		return
	frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": desk_access}).insert(
		ignore_permissions=True
	)


def _seed_settings():
	settings = frappe.get_single(SETTINGS)
	settings.vpn_endpoint_host = frappe.conf.get("vpn_endpoint_host") or settings.vpn_endpoint_host
	settings.sync_token = "set in site_config" if frappe.conf.get("vpn_sync_token") else None
	settings.save(ignore_permissions=True)


def _seed_default_server_and_pool():
	interface = _default_interface()
	if frappe.db.exists("WireGuard Server", interface):
		return
	server = frappe.get_doc(
		{
			"doctype": "WireGuard Server",
			"interface_name": interface,
			"environment": frappe.conf.get("vpn_environment") or "dev",
		}
	).insert(ignore_permissions=True)
	_seed_default_pool(server)


def _seed_default_pool(server):
	address = ipaddress.ip_interface(server.address_cidr)
	frappe.get_doc(
		{
			"doctype": "Network Pool",
			"pool_name": f"pool-{server.interface_name}",
			"server": server.interface_name,
			"cidr": str(address.network),
			"gateway_ip": str(address.ip),
		}
	).insert(ignore_permissions=True)


def _default_interface():
	return frappe.conf.get("vpn_default_interface") or DEFAULT_INTERFACE
