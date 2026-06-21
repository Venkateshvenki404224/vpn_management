# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from vpn_management import allocation, crypto
from vpn_management.permissions import is_admin

SETTINGS = "VPN Settings"
KEYGEN_FIELD = "allow_server_keygen"


class VPNPeer(Document):
	"""A WireGuard peer whose desired state lives in the DB.

	On save the peer atomically claims the lowest free address from its server's
	pool (a row-locked ``allocated = 1``) and enqueues a reconcile that renders
	the full interface and applies it with ``wg syncconf``. Disabling or deleting
	the peer frees the address — the allocation row is kept, never deleted.
	"""

	def before_insert(self):
		self._maybe_generate_keys()

	def validate(self):
		self._validate_public_key()
		if self.enabled:
			self._ensure_allocation()
		else:
			self._disable()

	def after_insert(self):
		self._enqueue_reconcile()

	def on_update(self):
		self._enqueue_reconcile()

	def on_trash(self):
		self._release_allocation()
		self._enqueue_reconcile()

	@frappe.whitelist(methods=["POST"])
	def regenerate_keys(self):
		"""Rotate this peer's keypair server-side; never return the private key."""
		self.check_permission("write")
		# Server-side keygen writes the permlevel-1 private_key. A caller without
		# permlevel-1 write would have that new key silently reset on save (leaving
		# the public_key rotated but the keypair mismatched), so restrict to admins —
		# non-admins rotate client-side and update public_key. Mirrors create_peer.
		if not is_admin(frappe.session.user):
			frappe.throw(
				_("Only VPN Admin may regenerate keys; rotate client-side and update the public key."),
				frappe.PermissionError,
			)
		self.private_key, self.public_key = crypto.generate_keypair()
		self.save()
		return {"name": self.name, "public_key": self.public_key, "assigned_ip": self.assigned_ip}

	@frappe.whitelist(methods=["POST"])
	def disable(self):
		"""Disable the peer (frees its address, drops it from the interface)."""
		self.check_permission("write")
		self.enabled = 0
		self.save()
		return {"name": self.name, "status": self.status}

	def _maybe_generate_keys(self):
		if self.public_key or not _allow_server_keygen():
			return
		self.private_key, self.public_key = crypto.generate_keypair()

	def _validate_public_key(self):
		if not self.public_key:
			frappe.throw(_("Public Key is required (server key generation is disabled)."))
		if not crypto.is_valid_public_key(self.public_key):
			frappe.throw(_("Public Key must be a base64-encoded 32-byte X25519 key."))

	def _ensure_allocation(self):
		if self.ip_allocation:
			return
		claimed = allocation.claim(self.server, self.name)
		self.ip_allocation = claimed.name
		self.assigned_ip = claimed.ip_address
		if not self.allowed_ips:
			self.allowed_ips = f"{claimed.ip_address}/32"
		# Fresh claim (create or re-enable): back to in-flight until the reconcile
		# confirms it on the live interface, so a re-enabled peer never stays Disabled.
		self.status = "Pending"
		self.synced_to_interface = 0

	def _disable(self):
		self._release_allocation()
		self.status = "Disabled"
		self.synced_to_interface = 0

	def _release_allocation(self):
		if not self.ip_allocation:
			return
		allocation.release(self.ip_allocation)
		# Only drop the auto-derived /32; keep an operator's custom allowed_ips
		# (site-to-site / subnet routes) so disable doesn't wipe routing intent.
		if self.allowed_ips == f"{self.assigned_ip}/32":
			self.allowed_ips = None
		self.ip_allocation = None
		self.assigned_ip = None

	def _enqueue_reconcile(self):
		frappe.enqueue(
			"vpn_management.tasks.reconcile_interface",
			queue="long",
			enqueue_after_commit=True,
			job_id=f"reconcile-{self.server}",
			deduplicate=True,
			interface_name=self.server,
		)


def _allow_server_keygen():
	"""True unless an operator explicitly disabled key generation.

	A single applies its JSON default only while completely unsaved; once any
	other field is stored, a missing Check reads as 0. So resolve the flag
	against the declared default when no value has been persisted.
	"""
	stored = frappe.db.get_singles_dict(SETTINGS).get(KEYGEN_FIELD)
	if stored is None:
		stored = frappe.get_meta(SETTINGS).get_field(KEYGEN_FIELD).default
	return bool(cint(stored))
