# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""REST surface: CRUD honors roles and no response ever carries key material."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import get_decrypted_password

from vpn_management import allocation, api, crypto
from vpn_management.vpn_management.tests import fixtures


class TestPeerApi(IntegrationTestCase):
	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.ensure_user("machine@vpn.test", ["VPN API"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_api_caller_create_allocates_ip_and_hides_keys(self):
		frappe.set_user("machine@vpn.test")
		with patch("frappe.enqueue"):
			result = api.create_peer(peer_name="m1", server="wg8", public_key=crypto.generate_keypair()[1])
		self.assertNotIn("private_key", result)
		self.assertNotIn("preshared_key", result)
		self.assertTrue(result["assigned_ip"])
		self.assertEqual(result["owner_user"], "machine@vpn.test")

	def test_api_caller_must_supply_public_key(self):
		frappe.set_user("machine@vpn.test")
		with self.assertRaises(frappe.ValidationError):
			api.create_peer(peer_name="m2", server="wg8")

	def test_admin_keygen_stores_private_key_but_response_hides_it(self):
		with patch("frappe.enqueue"):
			result = api.create_peer(peer_name="adminpeer", server="wg8")
		self.assertNotIn("private_key", result)
		stored = get_decrypted_password("VPN Peer", result["name"], "private_key", raise_exception=False)
		self.assertTrue(stored)

	def test_revoke_frees_ip_and_marks_revoked(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="r1", server="wg8", public_key=crypto.generate_keypair()[1])
			revoked = api.revoke_peer(created["name"])
		self.assertEqual(revoked["status"], "Revoked")
		self.assertFalse(revoked["enabled"])
		self.assertFalse(frappe.db.get_value("VPN Peer", created["name"], "assigned_ip"))

	def test_delete_peer_removes_row(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="d1", server="wg8", public_key=crypto.generate_keypair()[1])
			api.delete_peer(created["name"])
		self.assertFalse(frappe.db.exists("VPN Peer", created["name"]))

	def test_regenerate_keys_rotates_public_key_without_leaking_private(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="g1", server="wg8")
			before = created["public_key"]
			rotated = api.regenerate_keys(created["name"])
		self.assertNotIn("private_key", rotated)
		self.assertNotEqual(rotated["public_key"], before)

	def test_regenerate_keys_denied_for_api_caller(self):
		# Non-admins lack permlevel-1 write, so server-side keygen would desync the
		# keypair; the guard must reject them outright.
		frappe.set_user("machine@vpn.test")
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="g2", server="wg8", public_key=crypto.generate_keypair()[1])
		with self.assertRaises(frappe.PermissionError):
			api.regenerate_keys(created["name"])

	def test_interface_status_excludes_server_private_key(self):
		status = api.interface_status("wg8")
		self.assertNotIn("server_private_key", status)
		self.assertEqual(status["interface_name"], "wg8")

	def test_list_servers_returns_safe_fields_only(self):
		servers = api.list_servers()
		names = {row["interface_name"] for row in servers}
		self.assertIn("wg8", names)
		# The admin console row must never carry the server private key.
		self.assertNotIn("server_private_key", servers[0])
		self.assertEqual(set(servers[0].keys()), set(api.SAFE_SERVER_FIELDS))

	def test_server_private_key_readable_only_by_vpn_admin(self):
		# The spec's "server_private_key unreadable to every role but VPN Admin" —
		# verified at the permission layer, not just the response allowlist.
		fixtures.ensure_user("vadmin@vpn.test", ["VPN Admin"])
		server = frappe.get_doc("WireGuard Server", "wg8")
		frappe.set_user("machine@vpn.test")  # VPN API
		self.assertNotIn(1, server.get_permlevel_access("read"))
		frappe.set_user("vadmin@vpn.test")  # VPN Admin
		self.assertIn(1, server.get_permlevel_access("read"))

	def test_get_peer_status_returns_live_fields(self):
		with patch("frappe.enqueue"):
			created = api.create_peer(peer_name="s1", server="wg8", public_key=crypto.generate_keypair()[1])
		status = api.get_peer_status(created["name"])
		self.assertEqual(status["name"], created["name"])
		self.assertIn("rx_bytes", status)
		self.assertNotIn("private_key", status)


class TestSelfServiceConfig(IntegrationTestCase):
	"""my_config_download / my_config_qr: self-scoped, complete, key-safe."""

	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		frappe.db.set_single_value("VPN Settings", "vpn_endpoint_host", "vpn.example.com")
		frappe.db.set_single_value("VPN Settings", "dns_servers", "1.1.1.1")
		fixtures.ensure_user("alice@vpn.test", ["VPN User"])
		fixtures.ensure_user("bob@vpn.test", ["VPN User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.response = frappe._dict()

	def _make_alice_peer(self, peer_name):
		# No public_key => the server generates the keypair, so private_key is stored
		# and the rendered [Interface] carries a real PrivateKey line.
		with patch("frappe.enqueue"):
			return api.create_peer(peer_name=peer_name, server="wg8", owner_user="alice@vpn.test")

	def test_download_renders_full_client_config(self):
		peer = self._make_alice_peer("cfg1")
		api.my_config_download(peer["name"])
		conf = frappe.response["filecontent"]
		self.assertIn("[Interface]", conf)
		self.assertIn("PrivateKey = ", conf)
		self.assertIn(f"Address = {peer['assigned_ip']}/32", conf)
		self.assertIn("DNS = 1.1.1.1", conf)
		self.assertIn("[Peer]", conf)
		self.assertIn(f"PublicKey = {self.server.server_public_key}", conf)
		self.assertIn("Endpoint = vpn.example.com:", conf)
		# The [Peer] AllowedIPs must be the CLIENT route (default 172.27.0.0/16), never the
		# server-side allowed_ips (the peer's own /32) — swapping them is the spec's named bug.
		self.assertIn("AllowedIPs = 172.27.0.0/16", conf)
		self.assertNotIn(f"AllowedIPs = {peer['assigned_ip']}/32", conf)
		self.assertEqual(frappe.response["type"], "download")
		self.assertTrue(frappe.response["filename"].endswith(".conf"))

	def test_custom_client_allowed_ips_is_not_swapped_for_server_side(self):
		peer = self._make_alice_peer("cfg1b")
		frappe.db.set_value("VPN Peer", peer["name"], "client_allowed_ips", "10.0.0.0/8")
		api.my_config_download(peer["name"])
		conf = frappe.response["filecontent"]
		self.assertIn("AllowedIPs = 10.0.0.0/8", conf)
		self.assertNotIn(f"AllowedIPs = {peer['assigned_ip']}/32", conf)

	def test_download_never_leaks_the_server_private_key(self):
		peer = self._make_alice_peer("cfg2")
		api.my_config_download(peer["name"])
		conf = frappe.response["filecontent"]
		server_private = get_decrypted_password("WireGuard Server", "wg8", "server_private_key")
		self.assertNotIn(server_private, conf)

	def test_qr_returns_inline_png(self):
		peer = self._make_alice_peer("cfg3")
		api.my_config_qr(peer["name"])
		png = frappe.response["filecontent"]
		self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
		self.assertEqual(frappe.response["content_type"], "image/png")
		self.assertEqual(frappe.response["display_content_as"], "inline")

	def test_cross_user_download_is_denied(self):
		peer = self._make_alice_peer("cfg4")
		frappe.set_user("bob@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			api.my_config_download(peer["name"])

	def test_cross_user_qr_is_denied(self):
		peer = self._make_alice_peer("cfg5")
		frappe.set_user("bob@vpn.test")
		with self.assertRaises(frappe.PermissionError):
			api.my_config_qr(peer["name"])

	def test_unconfigured_endpoint_surfaces_a_clear_message(self):
		peer = self._make_alice_peer("cfg6")
		with patch("vpn_management.api.client_config._endpoint_host", return_value=""):
			with self.assertRaises(frappe.ValidationError):
				api.my_config_download(peer["name"])

	def test_qr_is_built_from_the_rendered_config(self):
		# Magic bytes alone would pass for any PNG; assert the QR encodes the real conf.
		peer = self._make_alice_peer("cfg7")
		captured = {}
		render = api._qr_png

		def spy(text):
			captured["text"] = text
			return render(text)

		with patch("vpn_management.api.client_config._qr_png", side_effect=spy):
			api.my_config_qr(peer["name"])
		self.assertIn("[Interface]", captured["text"])
		self.assertIn("Endpoint = vpn.example.com:", captured["text"])
		self.assertEqual(
			captured["text"], api._render_client_config(frappe.get_doc("VPN Peer", peer["name"]))
		)

	def test_endpoint_brackets_ipv6_literal_only(self):
		self.assertEqual(api._format_endpoint("2001:db8::1", 44556), "[2001:db8::1]:44556")
		self.assertEqual(api._format_endpoint("203.0.113.5", 44556), "203.0.113.5:44556")
		self.assertEqual(api._format_endpoint("vpn.example.com", 44556), "vpn.example.com:44556")

	def test_address_prefix_matches_family(self):
		self.assertEqual(api._max_prefix("10.66.0.2"), 32)
		self.assertEqual(api._max_prefix("fd00::2"), 128)


class TestInfraApi(IntegrationTestCase):
	"""Server / pool CRUD wrappers: admin-gated, key-safe, allocation-preserving."""

	def setUp(self):
		self.server = fixtures.ensure_server("wg8")
		fixtures.ensure_user("machine@vpn.test", ["VPN API"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_upsert_server_creates_and_hides_private_key(self):
		frappe.db.delete("WireGuard Server", {"interface_name": "wg6"})
		with patch("frappe.enqueue"):
			result = api.upsert_server(interface_name="wg6", listen_port=44999, environment="dev")
		self.assertEqual(result["interface_name"], "wg6")
		self.assertEqual(result["listen_port"], 44999)
		# keygen ran on insert, but only the public half is ever returned.
		self.assertTrue(result["server_public_key"])
		self.assertNotIn("server_private_key", result)

	def test_upsert_server_edits_existing(self):
		with patch("frappe.enqueue"):
			api.upsert_server(interface_name="wg8", listen_port=45123, egress_interface="eth9")
		server = frappe.get_doc("WireGuard Server", "wg8")
		self.assertEqual(server.listen_port, 45123)
		self.assertEqual(server.egress_interface, "eth9")

	def test_get_server_returns_firewall_rules_without_key(self):
		view = api.get_server("wg8")
		self.assertNotIn("server_private_key", view)
		# Rules are seeded on creation; each row is the exact safe allowlist.
		self.assertTrue(view["firewall_rules"])
		for row in view["firewall_rules"]:
			self.assertEqual(set(row.keys()), set(api.SAFE_FIREWALL_FIELDS))

	def test_upsert_server_replaces_firewall_rules(self):
		rules = [
			{
				"rule_type": "MASQUERADE",
				"ip_table": "nat",
				"chain": "POSTROUTING",
				"spec": "-o {egress} -j MASQUERADE",
				"enabled": 1,
			}
		]
		with patch("frappe.enqueue"):
			view = api.upsert_server(interface_name="wg8", firewall_rules=rules)
		self.assertEqual(len(view["firewall_rules"]), 1)
		self.assertEqual(view["firewall_rules"][0]["rule_type"], "MASQUERADE")

	def test_create_with_explicit_empty_rules_stays_rules_less(self):
		# An explicit [] must mean "no rules", not silently re-seeded defaults on create.
		frappe.db.delete("WireGuard Server", {"interface_name": "wg6"})
		with patch("frappe.enqueue"):
			view = api.upsert_server(interface_name="wg6", firewall_rules=[])
		self.assertEqual(view["firewall_rules"], [])

	def test_non_admin_cannot_upsert_server(self):
		frappe.set_user("machine@vpn.test")  # VPN API is read-only on WireGuard Server
		with patch("frappe.enqueue"), self.assertRaises(frappe.PermissionError):
			api.upsert_server(interface_name="wg8", listen_port=40000)

	def test_non_admin_cannot_upsert_pool(self):
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		frappe.set_user("machine@vpn.test")  # VPN API has no Network Pool permission at all
		with patch("frappe.enqueue"), self.assertRaises(frappe.PermissionError):
			api.upsert_pool(pool_name="pool-wg8", server="wg8", cidr="10.66.0.0/29")

	def test_upsert_pool_creates_and_lists(self):
		frappe.db.delete("Network Pool", {"server": "wg8"})
		with patch("frappe.enqueue"):
			view = api.upsert_pool(
				pool_name="pool-wg8", server="wg8", cidr="10.66.0.0/29", gateway_ip="10.66.0.1"
			)
		self.assertEqual(view["cidr"], "10.66.0.0/29")
		self.assertEqual(view["reserved_ranges"], [])
		self.assertIn("pool-wg8", {pool["name"] for pool in api.list_pools(server="wg8")})

	def test_upsert_pool_preserves_allocations_across_edits(self):
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.make_peer("wg8")  # claims the lowest free address
		before = frappe.db.count("IP Allocation", {"server": "wg8"})
		allocated = frappe.db.get_value("IP Allocation", {"server": "wg8", "allocated": 1}, "name")
		# Edit the pool (add a reserved range), then re-materialize as the controller would.
		with patch("frappe.enqueue"):
			api.upsert_pool(
				pool_name="pool-wg8",
				server="wg8",
				cidr="10.66.0.0/29",
				gateway_ip="10.66.0.1",
				reserved_ranges=[{"start_ip": "10.66.0.6", "end_ip": "10.66.0.6", "reason": "printer"}],
			)
		allocation.materialize("pool-wg8")
		self.assertEqual(before, frappe.db.count("IP Allocation", {"server": "wg8"}))  # never deleted
		self.assertTrue(frappe.db.get_value("IP Allocation", allocated, "allocated"))  # claim survives

	def test_list_ip_allocations_summary_and_key_safety(self):
		fixtures.seed_pool("wg8", cidr="10.66.0.0/29", gateway="10.66.0.1")
		fixtures.make_peer("wg8")
		result = api.list_ip_allocations("wg8")
		summary = result["summary"]
		self.assertEqual(summary["allocated"], 1)
		self.assertGreaterEqual(summary["reserved"], 1)  # at least the gateway
		self.assertEqual(summary["total"], summary["allocated"] + summary["reserved"] + summary["free"])
		self.assertTrue(result["rows"])
		for row in result["rows"]:
			# The IP-map projection is a fixed 5-field allowlist — assert it exactly so a
			# widened SELECT (or a doc-level fetch) that could leak fields fails here.
			self.assertEqual(set(row.keys()), {"name", "ip_address", "allocated", "reserved", "peer"})
