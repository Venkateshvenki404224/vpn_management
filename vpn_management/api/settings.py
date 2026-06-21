# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Admin-gated read/write surface for the VPN Settings Single.

The SPA Settings page edits environment-wide WireGuard defaults (endpoint host,
default ports, keepalive, DNS, sync kill-switches) through these two endpoints.
Both work over an explicit safe-field allowlist that **excludes ``sync_token``**:
the real sync secret lives in ``site_config`` (``bench set-config
vpn_sync_token``); the DocType field is only an informational read-only mirror, so
it is never returned to the client and never written here.
"""

import frappe

from vpn_management.permissions import is_admin

SETTINGS = "VPN Settings"

# Editable, non-secret fields surfaced to the in-SPA Settings page. ``sync_token``
# is deliberately absent — it is a display mirror for a secret kept in site_config,
# so it is neither read back to the client nor accepted as a write.
SAFE_SETTINGS_FIELDS = (
	"environment",
	"egress_interface",
	"default_listen_port",
	"allow_server_keygen",
	"wg_dir",
	"vpn_endpoint_host",
	"multiport_redirect_ports",
	"redirect_target_port",
	"dns_servers",
	"default_keepalive",
	"status_poll_interval_min",
	"sync_enabled",
	"sync_requires_local",
)


@frappe.whitelist(methods=["GET"])
def get_vpn_settings() -> dict:
	"""Return the editable VPN Settings (safe fields only; never the sync token)."""
	_require_admin()
	settings = frappe.get_cached_doc(SETTINGS)
	return _settings_view(settings)


@frappe.whitelist(methods=["POST"])
def upsert_vpn_settings(
	environment: str | None = None,
	egress_interface: str | None = None,
	default_listen_port: int | None = None,
	allow_server_keygen: int | None = None,
	wg_dir: str | None = None,
	vpn_endpoint_host: str | None = None,
	multiport_redirect_ports: str | None = None,
	redirect_target_port: int | None = None,
	dns_servers: str | None = None,
	default_keepalive: int | None = None,
	status_poll_interval_min: int | None = None,
	sync_enabled: int | None = None,
	sync_requires_local: int | None = None,
) -> dict:
	"""Persist the safe VPN Settings fields (admin-gated); the response hides the token.

	Only fields named in the signature can be written, so ``sync_token`` and any key
	material can never be set through this path. ``None`` means "leave as is"; ``0`` is
	a real value (a Switch toggled off), so checks persist correctly.
	"""
	_require_admin()
	settings = frappe.get_doc(SETTINGS)
	settings.check_permission("write")
	values = {
		"environment": environment,
		"egress_interface": egress_interface,
		"default_listen_port": default_listen_port,
		"allow_server_keygen": allow_server_keygen,
		"wg_dir": wg_dir,
		"vpn_endpoint_host": vpn_endpoint_host,
		"multiport_redirect_ports": multiport_redirect_ports,
		"redirect_target_port": redirect_target_port,
		"dns_servers": dns_servers,
		"default_keepalive": default_keepalive,
		"status_poll_interval_min": status_poll_interval_min,
		"sync_enabled": sync_enabled,
		"sync_requires_local": sync_requires_local,
	}
	for field, value in values.items():
		if value is not None:
			settings.set(field, value)
	settings.save()
	return _settings_view(settings)


def _settings_view(settings) -> dict:
	"""Project the Single onto the safe allowlist — the only fields that leave here."""
	return {field: settings.get(field) for field in SAFE_SETTINGS_FIELDS}


def _require_admin() -> None:
	if not is_admin(frappe.session.user):
		frappe.throw(frappe._("Not permitted to manage VPN settings."), frappe.PermissionError)
