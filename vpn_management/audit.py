# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Append-only audit trail for privileged VPN actions.

Every bring-up, syncconf, poll, and keygen records one ``VPN Audit Log`` row —
actor, redacted argv, result, and the in-use allocation count at run time (so a
mass wipe is detectable after the fact). Writes use ``ignore_permissions=True``:
the doctype is UI read-only and only the Administrator may prune it.
"""

import re

import frappe

# WireGuard keys are 32 bytes → 44-char base64 (43 chars + "=" padding). Never
# let one reach a log row, regardless of where the text came from.
_WG_KEY = re.compile(r"[A-Za-z0-9+/]{42,43}=")


def record(action, target, result, *, argv=None, detail=None, in_use_count=None):
	"""Insert one audit row; never let logging failure break the caller."""
	try:
		frappe.get_doc(
			{
				"doctype": "VPN Audit Log",
				"action": action,
				"target": target,
				"result": result,
				"actor": frappe.session.user,
				"source_ip": getattr(frappe.local, "request_ip", None),
				"argv_redacted": redact(argv),
				"detail": redact(detail),
				"in_use_count_at_run": in_use_count,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="VPN Audit Log write failed", message=f"{action} {target} {result}")


def redact(text):
	"""Mask anything shaped like a WireGuard key in free text."""
	if text is None:
		return None
	return _WG_KEY.sub("***", str(text))
