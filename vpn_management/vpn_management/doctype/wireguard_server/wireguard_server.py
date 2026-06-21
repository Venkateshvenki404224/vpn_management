# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

from vpn_management import crypto, firewall

INTERFACE_PATTERN = re.compile(r"^wg[0-9]+$")
ENVIRONMENT_CIDR = {"dev": "172.27.0.1/16", "prod": "172.30.0.1/16"}


class WireGuardServer(Document):
	"""A WireGuard interface whose desired state lives in the DB.

	The live kernel interface is a reconciled artifact: every save enqueues the
	background reconcile (:func:`vpn_management.tasks.reconcile_interface`) rather
	than touching the kernel inline. On creation its firewall rules are seeded
	from :mod:`vpn_management.firewall`.
	"""

	def before_insert(self):
		self._generate_keypair()
		firewall.seed_rules(self)

	def validate(self):
		self._validate_interface_name()
		self._validate_listen_port()
		self._apply_default_address_cidr()

	def on_update(self):
		self._enqueue_provision()

	@frappe.whitelist(methods=["POST"])
	def bring_up(self):
		"""Converge the live interface up from the DB (idempotent reconcile)."""
		self.check_permission("write")
		self._enqueue_provision()
		return {"interface": self.interface_name, "queued": True}

	@frappe.whitelist(methods=["POST"])
	def bring_down(self):
		"""Tear the live interface down (runs the firewall PostDown)."""
		self.check_permission("write")
		# A DISTINCT job_id from the reconcile family (reconcile-{iface}): sharing it
		# under deduplicate=True would let a queued reconcile silently swallow the
		# tear-down (or vice versa) — opposite operations must not dedup each other.
		frappe.enqueue(
			"vpn_management.tasks.bring_down_interface",
			queue="long",
			enqueue_after_commit=True,
			job_id=f"bring-down-{self.interface_name}",
			deduplicate=True,
			interface_name=self.interface_name,
		)
		return {"interface": self.interface_name, "queued": True}

	def _generate_keypair(self):
		if self.server_private_key:
			return
		self.server_private_key, self.server_public_key = crypto.generate_keypair()

	def _validate_interface_name(self):
		if not INTERFACE_PATTERN.match(self.interface_name or ""):
			frappe.throw(_("Interface Name must look like wg0, wg1, … (wg followed by a number)."))

	def _validate_listen_port(self):
		if not 1 <= (self.listen_port or 0) <= 65535:
			frappe.throw(_("Listen Port must be between 1 and 65535."))

	def _apply_default_address_cidr(self):
		if not self.address_cidr:
			self.address_cidr = ENVIRONMENT_CIDR.get(self.environment, ENVIRONMENT_CIDR["dev"])

	def _enqueue_provision(self):
		frappe.enqueue(
			"vpn_management.tasks.reconcile_interface",
			queue="long",
			enqueue_after_commit=True,
			job_id=f"reconcile-{self.interface_name}",
			deduplicate=True,
			interface_name=self.interface_name,
		)
