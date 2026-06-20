# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""In-app X25519 keypair generation, base64-encoded for WireGuard.

Generating keys here (instead of shelling out to ``wg genkey``) keeps the
sidecar's verb set minimal — the agent never needs a key-handling verb.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def generate_keypair():
	"""Return a ``(private_key, public_key)`` base64 pair, WireGuard-compatible."""
	private = X25519PrivateKey.generate()
	return _encode_private(private), _encode_public(private.public_key())


def public_key_for(private_key):
	"""Derive the base64 public key for a base64 WireGuard private key."""
	private = X25519PrivateKey.from_private_bytes(base64.b64decode(private_key))
	return _encode_public(private.public_key())


def _encode_private(private):
	raw = private.private_bytes(
		serialization.Encoding.Raw,
		serialization.PrivateFormat.Raw,
		serialization.NoEncryption(),
	)
	return base64.b64encode(raw).decode("ascii")


def _encode_public(public):
	raw = public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
	return base64.b64encode(raw).decode("ascii")
