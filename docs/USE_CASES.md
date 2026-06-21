# What `vpn_management` is for — usefulness & real-world use cases

A plain-language answer to *"what problem does this app solve, who would deploy it, and where?"* —
with concrete deployment scenarios drawn from how the app actually works.

> New to the project? Read the [README](../README.md) for the architecture and security model, and the
> [Developer Guide](DEVELOPMENT.md) for a live end-to-end trace. This doc is the "why and where".

---

## What it is, in one paragraph

`vpn_management` is a **Frappe-native control plane for WireGuard**. You manage a whole fleet of
WireGuard peers (servers, IP pools, clients) as ordinary DocTypes from the Frappe Desk, hand each user a
self-service portal where they download their own `.conf` or scan a QR straight into the WireGuard app,
and drive the same operations from a token-authenticated REST API — while the only component allowed to
touch the kernel is **one minimal, validated sidecar** behind a uid-scoped unix socket. The Frappe
database is the source of truth; the live interface is a reconciled artifact converged with diff-only
`wg syncconf`. You never hand-edit `wg0.conf` again.

---

## What it's useful for

- **Centralized fleet management with the DB as the source of truth.** Peers, servers, and IP pools are
  rows you can list, search, audit, and permission like any other Frappe data. A render → `wg syncconf`
  reconcile converges the running interface toward the database — never the other way around.
- **Safe multi-user self-service.** Users log in at `/vpn` and see **only the peers they own**, enforced
  independently at five layers. Private keys never appear in any list, API response, or audit row.
- **Automation via a real REST API.** Every operation — create/revoke/delete peers, read live status,
  reconcile — is a type-hinted, token-authenticated endpoint with explicit HTTP methods and no
  `allow_guest` anywhere. Provisioning can be wired into signup, CI, or device-onboarding flows.
- **An auditable privilege boundary instead of broad host sudo.** The Frappe containers stay
  unprivileged. The lone `wg-agent` sidecar exposes a *closed four-verb set* (`up`, `down`, `syncconf`,
  `show`) and re-validates every argument before it reaches the kernel. Every privileged action lands in
  an append-only audit log.
- **An IP-allocation model that structurally cannot be bulk-wiped.** Addresses are claimed with a
  row-locked `SELECT … FOR UPDATE` from a materialized pool, and allocation is UPSERT-only — the
  "a fresh sync deleted every allocation" class of incident simply has no code path.

---

## Who it's for

| If you are… | …this app gives you |
|---|---|
| A **platform / infra team** running remote access for engineers | Desk-managed peers, per-user self-service, offboarding by one click, a full audit trail. |
| A **SaaS / platform operator** offering VPN to customers | Per-tenant isolation by `owner_user`, API-driven provisioning, idempotent allocation. |
| An **MSP / IT shop** managing access for several clients | Role-scoped admin, revoke-not-delete for audit, firewall/redirect config as data. |
| A **homelab / self-hoster** | A standalone systemd install, one `wg0`, a clean UI instead of hand-edited config. |
| A **security-conscious org** replacing a hand-rolled `wg0.conf` + sudo setup | The footguns of the DIY approach designed out (see the last scenario below). |

---

## Real-world deployment scenarios

Each scenario reads as **Situation → How the app is used → Why it fits**. Every feature named below
exists today; see the [README](../README.md) for the full reference.

### 1 · Remote-access VPN for a distributed engineering team

**Situation.** A 40-person engineering org needs every developer's laptop and phone on a private network
to reach internal services, with clean onboarding and instant offboarding.

**How it's used.** An admin creates a `VPN Peer` per device from the Desk (or bulk via the API). Each
developer logs in to `/vpn`, sees only their own peers, and self-serves the `.conf` download or QR — no
key material ever passes through a chat or email. On offboarding, the admin runs `revoke_peer` (keeps the
audit trail) or `delete_peer`; the IP is freed back to the pool and dropped from the interface on the
next reconcile. `poll_status` (cron `*/5`) shows last handshake and transfer per peer, so "is this device
still connecting?" is answerable from the Desk.

**Why it fits.** Self-service removes the admin from the per-device config loop; five-layer isolation
means one user can never see another's config; the audit log answers "who had access, when".

### 2 · Multi-tenant "VPN-as-a-service" for a SaaS / platform

**Situation.** A platform wants to give each customer a set of WireGuard peers as part of its product,
provisioned automatically on signup, with hard isolation between tenants. This is the use case the app
was originally built to serve — a faithful, hardened replacement for a hand-rolled multi-tenant stack.

**How it's used.** The signup flow calls `create_peer` over the REST API with the customer's
`owner_user`; atomic allocation hands out the next free IP under a row lock so concurrent signups never
collide. Each customer's portal and API view is scoped to their own peers by `owner_user` and enforced at
five independent layers. Periodic reconciliation of pools runs through the hardened `sync_network`
endpoint — **UPSERT-only**, behind five gates (kill-switch → loopback-only → constant-time token compare
→ role check), so it can refresh allocations but is structurally incapable of deleting them.

**Why it fits.** The per-tenant scoping and idempotent, never-destructive sync are exactly the
properties a multi-tenant operator needs — and are the two things the legacy stack got wrong.

### 3 · Edge / IoT device fleet phone-home

**Situation.** Thousands of field devices (kiosks, sensors, routers) sit behind NAT and need a stable,
reachable private address to phone home to a control server.

**How it's used.** Each device generates its **own** keypair locally and registers via `create_peer`
with its client-generated public key — the server never takes custody of device private keys. Atomic
allocation assigns each device a stable `/32` from the pool. The default persistent keepalive (`25s`)
holds the NAT mapping open so the control plane can reach devices that never have a public IP.

**Why it fits.** Bring-your-own-public-key keeps key custody at the edge, allocation is collision-free at
fleet scale, and the API makes enrollment a single scriptable call per device.

### 4 · Time-boxed contractor / vendor access

**Situation.** An external contractor needs access to one internal subnet for a two-week engagement, and
nothing should linger afterward.

**How it's used.** Create a single peer, set its server-side `allowed_ips` to scope reach to just the
subnet they need, and hand them a QR. When the engagement ends, `revoke_peer` flips status (preserving the
audit record of the whole engagement) or `delete_peer` removes it outright and returns the IP to the pool.

**Why it fits.** Per-peer `allowed_ips` limits blast radius, revoke-not-delete keeps a defensible record,
and the whole lifecycle is two operations.

### 5 · Self-hosting / homelab (single admin)

**Situation.** One person wants a tidy way to run a personal WireGuard server across their devices without
editing `wg0.conf` by hand or wiring up broad sudo.

**How it's used.** Install in **standalone mode** (`agentd` as a root systemd unit, same socket
contract), provision one `wg0`, and manage everything from the Desk. The built-in multiport UDP redirect
(`333,666,999,3333,4444 → 44556`) helps connections slip through restrictive networks that only allow a
few ports.

**Why it fits.** A clean UI and a single privileged unit replace a pile of hand-edited config and sudoers
entries — even for a fleet of one.

### 6 · Hardened replacement for a legacy hand-rolled stack

**Situation.** You already run WireGuard via a bespoke script + REST wrapper: secrets in git, a broad
`www-data` sudo grant, and an allocations store that a bad sync once wiped. You want the same capability
without the scars.

**How it's used.** Adopt `vpn_management` as a clean-room replacement. Each legacy footgun maps to a
structural fix:

| Legacy footgun | How this app removes it |
|---|---|
| A `deleteMany() + insertMany()` sync wiped all allocations | Reconcile is **UPSERT-only**; no code path bulk-deletes allocations. |
| Broad `www-data` sudo (`wg`, `wg-quick`, `cat`, `git`, …) | Privilege shrinks to **four validated verbs** on a uid-scoped socket — no host sudo. |
| Secrets committed to git | Keys live in encrypted `Password` fields; tokens/endpoint live in `site_config`, never web-served. |
| Token leak → remote `/syncnetwork` wipe | `sync_network` sits behind **5 independent gates** and cannot delete. |
| API + `wg` fused in one host-net container | API runs in **unprivileged** containers; only the lone sidecar is privileged. |
| Private keys leaked through API responses | Responses are built from an explicit **safe-field allowlist**; `Password` fields are never serialized. |

**Why it fits.** This is the use case the app was designed for — faithful capability, footguns designed
out. See the README's [Security model](../README.md#security-model--footguns-designed-out) for the full table.

---

## What it is *not* for

Honest boundaries, so you can tell quickly if this is the wrong tool:

- **It manages WireGuard on a host, not a mesh.** The privileged sidecar is `network_mode: host` driving
  one host's kernel and iptables. If you want a peer-to-peer mesh / overlay with automatic NAT traversal
  and a coordination plane (Tailscale, Netbird, Nebula class), this is a different shape of tool.
- **One control plane, one (or a few) interfaces — not multi-region orchestration.** It excels at
  managing a fleet of *peers* on a server, not at orchestrating many independent VPN servers across
  regions from a single pane.
- **It assumes Frappe.** The value comes from DocTypes, roles, the Desk, the portal, and background jobs.
  If you don't want a Frappe app in your stack, the fit is poor.
- **Don't point a dev install at a production interface.** The sidecar drives the host's real kernel —
  always use a throwaway interface on an isolated subnet/port for testing (see
  [DEVELOPMENT.md §1](DEVELOPMENT.md#1-prerequisites)).

---

## Where to go next

- **[README](../README.md)** — architecture, the socket-spine security model, data model, API reference.
- **[Developer Guide](DEVELOPMENT.md)** — prerequisites, local setup, and a live trace of what happens
  in the database and containers when a peer is added.
