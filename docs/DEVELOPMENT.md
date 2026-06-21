# Developer Guide & End-to-End Walkthrough

A hands-on guide to getting `vpn_management` running locally, plus a **live walkthrough of what
actually happens — in the database and inside the containers — when a peer is added.**

> Every terminal block below is **real output** captured from a running stack, scoped to a throwaway
> `wg9` interface. Nothing here brings up production WireGuard or prints any key material.

**Contents**
1. [Prerequisites](#1-prerequisites)
2. [The mental model](#2-the-mental-model-30-seconds)
3. [Getting started — setup](#3-getting-started--setup)
4. [The privilege boundary, seen live](#4-the-privilege-boundary-seen-live)
5. [Walkthrough: what happens when a peer is added](#5-walkthrough-what-happens-when-a-peer-is-added)
6. [Inspecting a running system (read-only cheat-sheet)](#6-inspecting-a-running-system-read-only-cheat-sheet)
7. [Testing](#7-testing)
8. [Gotchas](#8-gotchas-the-ones-that-cost-real-time)
9. [File map](#9-file-map)

---

## 1. Prerequisites

### Host / kernel
| Requirement | Why |
|---|---|
| Linux kernel **≥ 5.6** | WireGuard is in-tree from 5.6; the agent's `SYS_MODULE` cap loads it if needed. |
| **Docker + Docker Compose v2** | The control plane and the `wg-agent` sidecar run as containers. |
| Free **UDP port** (default `44556`) + redirect ports `333,666,999,3333,4444` | The interface listen port and the multiport redirect. |
| Outbound NIC name (default `eth0`) | MASQUERADE egress; set it to your real egress in **VPN Settings**. |
| `git` | To fetch the app. |

### Frappe stack
| Requirement | Notes |
|---|---|
| A **Frappe v16 bench** | Docker bench (compose) **or** a standalone `bench` with `env/` + `sites/`. `deploy/install.sh` auto-detects which. |
| **Python ≥ 3.14** | Used by Frappe. The sidecar ships its own stdlib-only `python3` (Debian bookworm) — no app deps inside it. |
| Python deps `qrcode`, `Pillow` | For the portal's `.conf`/QR. Declared in `pyproject.toml`; installed by `bench setup requirements`. |
| **Developer mode** on the site | `bench set-config -g developer_mode 1` — required to materialize DocType JSON via `migrate`. |

### Knowledge you'll want
- **Frappe basics** — DocTypes, controllers, `bench`, the Desk UI, background jobs (RQ).
- **WireGuard basics** — `[Interface]`/`[Peer]` config, `wg`, `wg-quick`, `wg syncconf`.

### Secrets to have ready (never committed; live in `site_config`)
```bash
bench --site <site> set-config vpn_endpoint_host '<public DNS clients dial>'   # required — install fails loudly without it
bench --site <site> set-config vpn_sync_token    '<random secret>'             # required for sync_network
```

> ⚠️ **On a host that already runs production WireGuard:** the `wg-agent` is `network_mode: host`, so a
> `provision`/reconcile drives the **host's** kernel and iptables. Never point a dev install at `wg0` /
> the prod CIDR on such a host. Use a throwaway interface (`wg9`) on an isolated subnet + unused port, and
> tear it down afterwards. This guide does exactly that.

---

## 2. The mental model (30 seconds)

> **The Frappe database is the source of truth; the live kernel interface is a reconciled artifact.**

You never edit `wg0.conf` by hand. You edit **DocTypes** (servers, peers, pools). A background job renders
the full conf from those rows and converges the running interface toward it with diff-only `wg syncconf`.
The only component that may touch the kernel is one **`wg-agent` sidecar** exposing a closed four-verb set
over a uid-scoped unix socket. See the [architecture section in the README](../README.md#architecture) for
the full diagram.

---

## 3. Getting started — setup

### 3.1 Get the app into the bench

Bind-mounted dev bench (edit in place, no rebuild):
```bash
cd $PATH_TO_YOUR_BENCH
bench get-app vpn_management <repo-url> --branch main      # or symlink/clone into ./apps
bench set-config -g developer_mode 1
```

### 3.2 Set the required config (before install)
```bash
bench --site <site> set-config vpn_endpoint_host 'vpn.example.com'
bench --site <site> set-config vpn_sync_token    "$(openssl rand -hex 32)"
```
`after_install` **aborts loudly** if `vpn_endpoint_host` is unset — a peer cannot be handed a working
client config without it. (Under CI/tests the gate downgrades to a warning.)

### 3.3 Bring up the sidecar **and** install — one command

Run [`deploy/install.sh`](../deploy/install.sh) from the **bench root**. It auto-detects the mode:

```bash
./apps/vpn_management/deploy/install.sh            # auto
./apps/vpn_management/deploy/install.sh compose    # force compose mode
sudo ./apps/vpn_management/deploy/install.sh standalone   # force systemd mode
```

| Mode | What it does |
|---|---|
| **compose** | `docker compose -f docker-compose.yml -f apps/vpn_management/deploy/docker-compose.wg-agent.yml up -d --build wg-agent`, recreates `backend` + `queue-long` with the shared socket/volume mounts, waits for the socket, then `bench install-app`. |
| **standalone** | Installs `agentd` as a root `systemd` unit (`wg-agent.service`, `RuntimeDirectory=wg-agent`, passing the real bench uid via `WG_AGENT_SOCKET_UID`), waits for the socket, then `bench install-app` as the bench user. |

Either way the **bench `docker-compose.yml` is never edited** — the sidecar is layered on via `-f`. The
app's `after_install` then health-gates on `/run/wg-agent/agent.sock` and fails if the agent isn't up.

### 3.4 Verify the install
```bash
bench --site <site> list-apps           # shows vpn_management
bench --site <site> migrate             # materializes the 8 DocTypes
bench --site <site> clear-cache         # ALWAYS after a DocType JSON change
```

`after_install` seeds: the 4 roles, **VPN Settings**, a default `wg0` **WireGuard Server**, and its
**Network Pool**.

### 3.5 Provision the interface

```bash
bench --site <site> execute vpn_management.api.provision_server --kwargs '{"interface_name":"wg0"}'
```
`provision_server` materializes the pools and **enqueues** a background provision (`reconcile-{iface}`),
returning `{"queued": true}` immediately — it does **not** block on the kernel. The `queue-long` worker then
renders the `[Interface]` conf and brings the interface up via `wg-quick up` (running the firewall PostUp
once). The server keypair is generated earlier, when the WireGuard Server row is first created
(`before_insert`).

> On a production-WireGuard host, do this only against a throwaway interface on an isolated subnet/port.

---

## 4. The privilege boundary, seen live

This is the load-bearing security claim — let's verify it inside the running containers.

### 4.1 Only the sidecar is privileged

```console
$ for c in wg-agent backend queue-long; do docker inspect -f \
   '{{.Name}} NetworkMode={{.HostConfig.NetworkMode}} CapAdd={{.HostConfig.CapAdd}}' "$c"; done

strapay-helpdesk-wg-agent-1   NetworkMode=host                          CapAdd=[NET_ADMIN SYS_MODULE]
strapay_helpdesk_backend      NetworkMode=strapay-helpdesk_frappe_network   CapAdd=[]
strapay_helpdesk_queue-long   NetworkMode=strapay-helpdesk_frappe_network   CapAdd=[]
```

The Frappe containers have **no added capabilities** and stay on the bridge network. Only `wg-agent` holds
`NET_ADMIN` + `SYS_MODULE` and joins the host network namespace.

### 4.2 The agent runs as root; the socket is uid-scoped

```console
$ docker exec strapay-helpdesk-wg-agent-1 ps -o pid,user,args -C python3
    PID USER     COMMAND
      1 root     python3 /opt/wg-agent/agentd

$ docker exec strapay-helpdesk-wg-agent-1 ls -ln /run/wg-agent/
srw------- 1 1000 1000 0 Jun 20 21:55 agent.sock
```

`agentd` is PID 1, root. The socket is `srw-------` (mode `600`) owned by **uid 1000** — the `frappe`
user, and no one else, may connect.

### 4.3 The worker physically cannot run WireGuard

```console
$ docker exec strapay-helpdesk-wg-agent-1 sh -c 'for b in wg wg-quick iptables; do command -v $b; done'
/usr/bin/wg
/usr/bin/wg-quick
/usr/sbin/iptables

$ docker exec strapay_helpdesk_backend  sh -c 'for b in wg wg-quick iptables; do command -v $b || echo "NOT INSTALLED"; done'
NOT INSTALLED
NOT INSTALLED
NOT INSTALLED
```

Even if the worker were fully compromised, it has no `wg`/`iptables` binaries — its only route to the
kernel is the four validated verbs on the socket.

### 4.4 The socket boundary, exercised

Talking to the socket directly (from inside the sidecar) shows the closed verb set and per-argument
validation rejecting anything off-script:

```console
$ docker exec -i strapay-helpdesk-wg-agent-1 python3   # send three JSON requests to agent.sock

1) VALID verb   -> show wg9
   request : {"verb":"show","args":["wg9"]}
   reply   : {"ok": false, "code": 1, "stdout": "", "stderr": "Unable to access interface: No such device\n"}

2) UNKNOWN verb -> closed verb set rejects it
   request : {"verb":"reboot","args":[]}
   reply   : {"ok": false, "error": "unknown verb: 'reboot'"}

3) INJECTION in the interface arg -> per-arg validation rejects it
   request : {"verb":"show","args":["evil; rm -rf /"]}
   reply   : {"ok": false, "error": "invalid interface: 'evil; rm -rf /'"}
```

- **(1)** A valid verb is executed — the agent ran `wg show wg9` and faithfully relayed the result (`wg9`
  is down here, hence "No such device").
- **(2)** `reboot` isn't in `ALLOWED_VERBS = ("up", "syncconf", "show")` → rejected before anything runs.
- **(3)** The interface arg must match `^wg[0-9]+$`; the shell-injection payload never reaches a shell.

There is no `keygen`, `cat`, `git`, or arbitrary-exec verb — keypairs are generated in-app via the `cryptography`
library's X25519, so the agent's surface stays this small. For `up`/`syncconf` the agent *also* validates the conf
body against a default-deny allowlist and reduces any `PostUp`/`PostDown` to constrained `iptables`-only
calls (see [`deploy/wg-agent/agentd`](../deploy/wg-agent/agentd)).

---

## 5. Walkthrough: what happens when a peer is added

When you click **Add VPN Peer** in the Desk (or `POST create_peer`), this is the full path:

```
 Desk form / REST create_peer
        │  doc.insert()
        ▼
 VPNPeer.validate ──► allocation.claim()         # atomic IP allocation (SELECT … FOR UPDATE)
        │
        ▼
 VPNPeer.after_insert / on_update
        │  frappe.enqueue("reconcile_interface", queue="long",
        │                 enqueue_after_commit=True, job_id="reconcile-wg9", deduplicate=True)
        ▼
 queue-long worker ──► tasks.reconcile_interface()
        │  render full conf from DB  →  sha256 vs config_hash
        ▼
 privileged.py ──JSON over unix socket──► agentd  (validates every arg)
        │                                   │
        │   interface_up == 0 → wg-quick up │   (runs firewall PostUp once)
        │   interface_up == 1 → wg syncconf │   (diff-only; preserves handshakes)
        ▼                                   ▼
 status=Up, peers synced, VPN Audit Log row written     wg0 now carries the peer
```

Let's watch the parts that don't need the kernel — they're the same whether or not the interface is up.

### Step 0 — the starting state (real rows)

The throwaway `wg9` server has a `/29` pool (`10.77.0.0/29`). `wg9-10.77.0.1` is the **reserved gateway**;
`wg9-10.77.0.2` is already **allocated** to an existing peer:

```console
$ bench --site frontend console      # IP Allocation rows for wg9
{"name": "wg9-10.77.0.2", "ip_address": "10.77.0.2", "allocated": 1, "reserved": 0, "peer": "PEER-00003"}
{"name": "wg9-10.77.0.1", "ip_address": "10.77.0.1", "allocated": 0, "reserved": 1, "peer": null}
{"name": "wg9-10.77.0.3", "ip_address": "10.77.0.3", "allocated": 0, "reserved": 0, "peer": null}
{"name": "wg9-10.77.0.4", "ip_address": "10.77.0.4", "allocated": 0, "reserved": 0, "peer": null}
...
free/total: 4 / 6
```

Every candidate address is a row (materialized once, **never bulk-deleted**), so "is this IP used?" is a
plain column read and allocation is a single row-locked `UPDATE`.

### Step 1 + 2 — add a peer → atomic allocation (live, reversible)

Here we add a peer with the kernel path neutralized (`frappe.enqueue` patched to a no-op) and roll the
whole thing back, so it's a pure, side-effect-free demonstration of the allocation:

```console
$ bench --site frontend console
FREE addresses BEFORE add : 4

PEER created            : PEER-00004
  assigned_ip           : 10.77.0.3
  status                : Pending
  IP Allocation flipped : {'name': 'wg9-10.77.0.3', 'allocated': 1, 'peer': 'PEER-00004'}
FREE addresses AFTER add  : 3 (claimed the lowest free row via SELECT ... FOR UPDATE)

Rendered [Peer] block this peer adds to wg9.conf:
[Peer]
PublicKey = ooPiI8J60BsWqQxpt2f/5oSGRGI4yVhYmpATXCfKM0s=
AllowedIPs = 10.77.0.3/32

ROLLED BACK — nothing persisted (free count is back to 4).
```

What happened on `insert()`:
- `validate` called `allocation.claim()`, which `SELECT … WHERE allocated=0 AND reserved=0 ORDER BY
  ip_order LIMIT 1 FOR UPDATE` — locking the lowest free row (`.3`, since `.1` is reserved and `.2` taken)
  and flipping it to `allocated=1, peer=PEER-00004`. The row lock is the concurrency guard: two
  simultaneous creates can never grab the same address.
- The peer got `assigned_ip = 10.77.0.3`, `status = Pending`.

### Step 3 — the rendered conf

The reconcile job renders the **whole** `wg9.conf` from the DB — the `[Interface]` block (key, address,
listen port, firewall PostUp/PostDown) plus a `[Peer]` block per enabled peer. Structure (secrets shown as
placeholders — they are **never** logged or committed):

```ini
[Interface]
PrivateKey = <server private key — from an encrypted Password field>
Address    = 172.27.0.1/16
ListenPort = 44556
PostUp   = iptables -C FORWARD -i %i -j ACCEPT || iptables -A FORWARD -i %i -j ACCEPT
PostUp   = iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE || iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostUp   = iptables -t nat -C PREROUTING ... -m multiport --dports 333,666,999,3333,4444 -j REDIRECT --to-ports 44556 || iptables -t nat -A PREROUTING ...
PostDown = iptables -D FORWARD -i %i -j ACCEPT
...

[Peer]
PublicKey  = ooPiI8J60BsWqQxpt2f/5oSGRGI4yVhYmpATXCfKM0s=
AllowedIPs = 10.77.0.3/32
```

A `sha256(conf)` is compared with the server's stored `config_hash`: if unchanged **and** the interface is
up, the reconcile is a no-op. The PostUp rules are rendered idempotent (`-C … || -A …`) so a re-`up`
after a restart can't stack them.

### Step 4 — the background job

The controller never touches the socket itself. It enqueues:
```python
frappe.enqueue("vpn_management.tasks.reconcile_interface",
               queue="long", enqueue_after_commit=True,
               job_id=f"reconcile-{server}", deduplicate=True, interface_name=server)
```
- `enqueue_after_commit=True` — the job only runs once the DB row is durably committed.
- `job_id` + `deduplicate=True` — saving a peer five times fast collapses to **one** reconcile.

### Step 5 — the agent applies it (the kernel step)

`tasks.reconcile_interface` → `privileged.call(...)` → `agentd`, which branches:

| Interface state | Verb | Effect |
|---|---|---|
| down (`interface_up=0`) | `wg-quick up` | Creates the interface, runs the firewall **PostUp** once. |
| up (`interface_up=1`) | `wg syncconf` | Diff-only apply; **preserves live handshakes**, never re-runs PostUp (so the REDIRECT can't stack). |

You can watch the agent's view of the interface (read-only) the same way the `poll_status` cron does:
```console
$ docker exec -i strapay-helpdesk-wg-agent-1 python3   # {"verb":"show","args":["wg9","dump"]}
# once up, each [Peer] appears here as: <pubkey> <psk> <endpoint> <allowed-ips> <handshake> <rx> <tx> ...
```
`poll_status` (cron `*/5`) parses exactly this dump back onto the peers — `last_handshake`, `rx_bytes`,
`tx_bytes`, and `status` Active/Stale.

> **On this dev host the apply step is intentionally not wired through the worker:** `queue-long` is
> running **without** the socket/volume mounts (the compose fragment isn't layered here, to keep the
> production WireGuard untouched), so a real peer-add would enqueue a reconcile that can't reach the agent.
> The mounts are added automatically by `deploy/install.sh compose` on a clean target — see §4.1 vs. the
> empty mount lists below.

### Step 6 — the user gets their config

Once `status = Active`, the owner sees the peer at **`/vpn`** and downloads a ready `.conf` or scans a QR
straight into the WireGuard app. The portal query and the download endpoints never select key material.
See the [portal screenshots in the README](../README.md#2--self-service-portal-vpn-user).

---

## 6. Inspecting a running system (read-only cheat-sheet)

All safe; none mutate state. Scope `wg show` to your **own** interface — on a host-net agent, a bare
`wg show` would also list other interfaces on the host.

```bash
# Privilege model
docker inspect -f '{{.HostConfig.NetworkMode}} {{.HostConfig.CapAdd}}' <container>
docker exec <agent> ls -ln /run/wg-agent/                 # socket uid + mode (1000, 600)
docker exec <agent> ps -o pid,user,args -C python3        # agentd as root

# Where the worker's mounts should be (empty here = fragment not layered)
docker inspect -f '{{range .Mounts}}{{.Name}}->{{.Destination}} {{end}}' <queue-long> | tr ' ' '\n' | grep -Ei 'wg-agent|vpnstorage'

# DB is the source of truth — read it
bench --site <site> console      # frappe.get_all("VPN Peer", ...), frappe.get_all("IP Allocation", ...)

# Live interface (scope to YOUR iface)
docker exec <agent> wg show <wgN>

# Background jobs / scheduler
bench --site <site> show-pending-jobs
bench --site <site> doctor
```

---

## 7. Testing

```bash
# Frappe integration + crypto suite (run inside the backend container)
docker compose exec backend bench --site frontend run-tests --app vpn_management

# agentd security suite — stdlib only, the privilege boundary (no bench needed)
python3 apps/vpn_management/deploy/wg-agent/test_agentd.py
```
The backend container on this stack is **`strapay_helpdesk_backend`**; the dev site is `frontend`. The
site needs `bench --site frontend set-config allow_tests true` once. Tests target a throwaway interface
(overridable via `frappe.conf.vpn_default_interface`) and roll back, so the live scheduler never sees test
artifacts.

---

## 8. Gotchas (the ones that cost real time)

- **Always `migrate` + `clear-cache` after any DocType JSON change** — the schema won't apply otherwise.
- **`queue-long` needs the socket *and* the `vpnstorage` mount** — it renders the conf into the shared
  volume *and* calls the agent. Without both, reconcile fails with `VpnAgentError`. `deploy/install.sh
  compose` adds them; a hand-rolled `up` that forgets the fragment will not.
- **A Single's unset `Check` reads 0** — `frappe.db.get_single_value` returns `0` for an unset checkbox,
  and a Single only applies its JSON default while *completely* unsaved. Resolve flags via
  `frappe.db.get_singles_dict(...).get(field)` with a meta-default fallback (see `api._flag`).
- **`syncconf` needs the interface already up** — it ignores `Address`/`PostUp`. The reconcile branches to
  `wg-quick up` when `interface_up` is false; `reconcile_all` self-heals this after a host restart.
- **`get_singles_dict` is `frappe.db.get_singles_dict`**, not `frappe.get_singles_dict`.
- **Byte counters and `ip_order` are `Long Int`** — a plain `Int` overflows on `172.27.x.x` (≈2.9e9) and
  on real transfer totals.
- **This dev host runs production WireGuard** — never provision `wg0` or use the prod CIDR here.

---

## 9. File map

| Path | Role |
|---|---|
| [`vpn_management/api.py`](../vpn_management/api.py) | Token REST surface + portal config/QR endpoints. |
| [`vpn_management/allocation.py`](../vpn_management/allocation.py) | Materialize pools; atomic `FOR UPDATE` claim/release. |
| [`vpn_management/tasks.py`](../vpn_management/tasks.py) | Reconcile / poll / self-heal background jobs + conf render. |
| [`vpn_management/privileged.py`](../vpn_management/privileged.py) | Unix-socket client to `agentd` (the spine). |
| [`vpn_management/audit.py`](../vpn_management/audit.py) | Append-only VPN Audit Log writer (key-redacted: actor, source IP, redacted argv, result, in-use count). |
| [`vpn_management/crypto.py`](../vpn_management/crypto.py) | In-app X25519 keygen (via the `cryptography` library). |
| [`vpn_management/firewall.py`](../vpn_management/firewall.py) | NAT / FORWARD / MASQUERADE / REDIRECT rule templates. |
| [`vpn_management/permissions.py`](../vpn_management/permissions.py) | Owner-scoped row-level access for VPN Peer. |
| [`vpn_management/install.py`](../vpn_management/install.py) | `after_install`: health-gate + seed roles/settings/server/pool. |
| [`vpn_management/www/vpn.{py,html}`](../vpn_management/www/) | Self-service portal at `/vpn`. |
| [`deploy/install.sh`](../deploy/install.sh) | One-command dual-mode installer. |
| [`deploy/docker-compose.wg-agent.yml`](../deploy/docker-compose.wg-agent.yml) | In-app compose fragment (layered, never edits the bench file). |
| [`deploy/wg-agent/agentd`](../deploy/wg-agent/agentd) | The root socket server — **the privilege boundary**. |

---

*New to the project? Read the [README](../README.md) first for the architecture and security model, then
come back here to set up and trace a peer end-to-end.*
