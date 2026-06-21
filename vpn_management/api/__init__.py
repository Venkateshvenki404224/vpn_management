# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""Public REST surface for vpn_management — a thin facade over focused submodules.

Every whitelisted endpoint is re-exported here so callers keep using the stable
``vpn_management.api.<endpoint>`` path while the implementation lives in cohesive
modules:

* :mod:`~vpn_management.api.peers` — peer CRUD + live status.
* :mod:`~vpn_management.api.infra` — WireGuard Server / Network Pool / IP map CRUD.
* :mod:`~vpn_management.api.client_config` — self-service ``.conf`` / QR streaming.
* :mod:`~vpn_management.api.network_sync` — the hardened ``sync_network``.

Frappe resolves the dotted path against this package, so the re-exported function
object — already carrying its ``@frappe.whitelist`` flag — is what gets called.
There is **no** ``allow_guest`` anywhere; callers are gated by the four VPN roles.
"""

from vpn_management.api.client_config import my_config_download, my_config_qr
from vpn_management.api.infra import (
	SAFE_FIREWALL_FIELDS,
	SAFE_POOL_FIELDS,
	SAFE_RESERVED_FIELDS,
	SAFE_SERVER_FIELDS,
	SERVER_FORM_FIELDS,
	get_pool,
	get_server,
	interface_status,
	list_ip_allocations,
	list_pools,
	list_servers,
	provision_server,
	reconcile_interface,
	upsert_pool,
	upsert_server,
)
from vpn_management.api.network_sync import sync_network
from vpn_management.api.peers import (
	SAFE_PEER_FIELDS,
	create_peer,
	delete_peer,
	get_peer,
	get_peer_status,
	list_peers,
	regenerate_keys,
	revoke_peer,
)

# Private render helpers the test-suite reaches through the facade (reads/calls).
# Patches that must take effect target the owning submodule (api.client_config.*).
from vpn_management.api.client_config import (  # isort: skip
	_endpoint_host,
	_format_endpoint,
	_max_prefix,
	_qr_png,
	_render_client_config,
)

__all__ = [
	"SAFE_FIREWALL_FIELDS",
	"SAFE_PEER_FIELDS",
	"SAFE_POOL_FIELDS",
	"SAFE_RESERVED_FIELDS",
	"SAFE_SERVER_FIELDS",
	"SERVER_FORM_FIELDS",
	"create_peer",
	"delete_peer",
	"get_peer",
	"get_peer_status",
	"get_pool",
	"get_server",
	"interface_status",
	"list_ip_allocations",
	"list_peers",
	"list_pools",
	"list_servers",
	"my_config_download",
	"my_config_qr",
	"provision_server",
	"reconcile_interface",
	"regenerate_keys",
	"revoke_peer",
	"sync_network",
	"upsert_pool",
	"upsert_server",
]
