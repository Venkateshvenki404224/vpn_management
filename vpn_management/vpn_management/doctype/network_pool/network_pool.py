# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import ipaddress

import frappe
from frappe import _
from frappe.model.document import Document


class NetworkPool(Document):
	"""A CIDR whose host addresses are materialized into IP Allocation rows.

	Saving a pool enqueues the idempotent ``materialize_pool`` job rather than
	walking the CIDR inline — a /16 is 65k rows, so the work belongs on the long
	queue. Materialization never deletes rows, which is what structurally
	prevents the old ``deleteMany()`` allocation-wipe incident.
	"""

	def validate(self):
		network = self._validate_cidr()
		self._guard_cidr_change()
		self._validate_gateway(network)
		self._validate_reserved_ranges(network)

	def on_update(self):
		self._enqueue_materialize()

	def _validate_cidr(self):
		try:
			return ipaddress.ip_network(self.cidr, strict=False)
		except ValueError:
			frappe.throw(_("CIDR {0} is not a valid network.").format(self.cidr))

	def _guard_cidr_change(self):
		# A materialized CIDR cannot shrink/move without orphaning allocatable rows
		# outside the new network, so freeze it once any IP Allocation row exists.
		if self.is_new() or not self.has_value_changed("cidr"):
			return
		if frappe.db.exists("IP Allocation", {"pool": self.name}):
			frappe.throw(_("CIDR cannot change after the pool is materialized; create a new pool."))

	def _validate_gateway(self, network):
		if not self.gateway_ip:
			return
		if self._parse_ip(self.gateway_ip, _("Gateway")) not in network:
			frappe.throw(_("Gateway {0} is outside {1}.").format(self.gateway_ip, self.cidr))

	def _validate_reserved_ranges(self, network):
		for row in self.reserved_ranges:
			start = self._parse_ip(row.start_ip, _("Reserved range start"))
			end = self._parse_ip(row.end_ip, _("Reserved range end"))
			if int(start) > int(end):
				frappe.throw(_("Reserved range {0}-{1} is inverted.").format(row.start_ip, row.end_ip))
			if start not in network or end not in network:
				frappe.throw(
					_("Reserved range {0}-{1} is outside {2}.").format(row.start_ip, row.end_ip, self.cidr)
				)

	def _parse_ip(self, value, label):
		try:
			return ipaddress.ip_address(value)
		except ValueError:
			frappe.throw(_("{0} {1} is not a valid IP address.").format(label, value))

	def _enqueue_materialize(self):
		frappe.enqueue(
			"vpn_management.tasks.materialize_pool",
			queue="long",
			enqueue_after_commit=True,
			job_id=f"materialize-{self.name}",
			deduplicate=True,
			pool_name=self.name,
		)
