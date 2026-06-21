# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import base64

from frappe.tests import UnitTestCase

from vpn_management import crypto


class TestCrypto(UnitTestCase):
	def test_keypair_is_32_byte_base64(self):
		private_key, public_key = crypto.generate_keypair()
		self.assertEqual(len(base64.b64decode(private_key)), 32)
		self.assertEqual(len(base64.b64decode(public_key)), 32)

	def test_public_key_derives_from_private(self):
		private_key, public_key = crypto.generate_keypair()
		self.assertEqual(crypto.public_key_for(private_key), public_key)

	def test_each_keypair_is_unique(self):
		first, _ = crypto.generate_keypair()
		second, _ = crypto.generate_keypair()
		self.assertNotEqual(first, second)
