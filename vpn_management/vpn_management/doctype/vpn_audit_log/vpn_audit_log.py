# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class VPNAuditLog(Document):
	"""Append-only record of every privileged VPN action.

	Rows are written with ``ignore_permissions=True`` from the background jobs
	and controllers; the UI is read-only. The log is pruned only by the
	Administrator — :meth:`on_trash` refuses every other actor so the trail
	cannot be quietly rewritten.
	"""

	def on_trash(self):
		if frappe.session.user != "Administrator":
			frappe.throw(
				_("Only the Administrator may delete VPN Audit Log entries."), frappe.PermissionError
			)

	@staticmethod
	def clear_old_logs(days=90):
		"""LogType hook: let Frappe's log clean-up prune rows past the retention.

		``default_log_clearing_doctypes`` only takes effect for a doctype whose
		controller implements this method, so without it the registered retention
		is a silent no-op and the table grows without bound.
		"""
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("VPN Audit Log")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))
