# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Boot + serve the frappe-ui VPN SPA at ``/vpn``.

The page itself carries no peer data: the Vue app reads everything it needs from
the owner-scoped REST surface in :mod:`vpn_management.api`. ``get_context`` only
seeds the boot payload the SPA needs to authenticate (CSRF), identify the
session, and degrade gracefully when the public endpoint is unconfigured.
Guests are redirected to the Frappe login rather than served the shell.
"""

from urllib.parse import quote

import frappe

SETTINGS = "VPN Settings"
no_cache = 1


def get_context(context):
	_reject_guest()
	context.no_cache = 1
	context.boot = _boot()
	return context


def _boot():
	return frappe._dict(
		{
			"csrf_token": frappe.sessions.get_csrf_token(),
			"session_user": frappe.session.user,
			"endpoint_ready": _endpoint_ready(),
			"site_name": frappe.local.site,
		}
	)


def _reject_guest():
	"""Send guests to login (carrying a redirect back) instead of the SPA shell."""
	if frappe.session.user != "Guest":
		return
	request = getattr(frappe.local, "request", None)
	path = request.path if request else "/vpn"
	frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(path)
	raise frappe.Redirect


def _endpoint_ready():
	settings = frappe.db.get_singles_dict(SETTINGS)
	return bool(settings.get("vpn_endpoint_host") or frappe.conf.get("vpn_endpoint_host"))
