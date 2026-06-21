# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class IPAllocation(Document):
	"""One host address in a pool. ``name`` is ``{server}-{ip_address}`` so the
	row is an idempotent upsert key — materialization re-runs without duplicates.

	The row is the source of truth for "is this address in use": a peer claims it
	with a row-locked ``allocated = 1`` and frees it with ``allocated = 0`` on
	delete/disable. The row itself is **never** deleted — that is the structural
	fix for the legacy allocation-wipe incident.
	"""

	pass
