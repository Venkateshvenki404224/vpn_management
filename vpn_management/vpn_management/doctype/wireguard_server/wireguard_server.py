# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

from vpn_management import crypto

INTERFACE_PATTERN = re.compile(r"^wg[0-9]+$")
ENVIRONMENT_CIDR = {"dev": "172.27.0.1/16", "prod": "172.30.0.1/16"}


class WireGuardServer(Document):
	"""A WireGuard interface whose desired state lives in the DB.

	The live kernel interface is a reconciled artifact: every save enqueues the
	background reconcile (:func:`vpn_management.tasks.provision_server`) rather
	than touching the kernel inline.
	"""

	def before_insert(self):
		self._generate_keypair()

	def validate(self):
		self._validate_interface_name()
		self._validate_listen_port()
		self._apply_default_address_cidr()

	def on_update(self):
		self._enqueue_provision()

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
