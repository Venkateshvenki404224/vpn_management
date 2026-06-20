# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class NetworkReservedRange(Document):
	"""An inclusive IPv4 range carved out of a pool so it is never auto-allocated."""

	pass
