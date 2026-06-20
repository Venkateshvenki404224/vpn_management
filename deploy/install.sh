#!/usr/bin/env bash
# One-command installer for vpn_management. Run from the BENCH ROOT.
#
# Dual-mode — the app and agentd are deployment-neutral; only HOW agentd is
# launched differs. The script auto-detects which applies (override with an
# explicit `compose` / `standalone` argument):
#
#   compose    : build + start the wg-agent sidecar, recreate backend/queue-long
#                with the shared socket+volume mounts, then `bench install-app`.
#   standalone : install agentd as a root systemd unit (same socket contract),
#                then `bench install-app` as the bench user.
#
# Either way the app's after_install health-gates on /run/wg-agent/agent.sock and
# fails loudly if the agent is not up.
set -euo pipefail

APP="vpn_management"
SITE="${SITE_NAME:-frontend}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTD="${SCRIPT_DIR}/wg-agent/agentd"
FRAGMENT="apps/${APP}/deploy/docker-compose.wg-agent.yml"
SOCKET="/run/wg-agent/agent.sock"
WG_DIR="/etc/wireguard"

log() { printf '==> %s\n' "$*"; }
die() {
	printf 'error: %s\n' "$*" >&2
	exit 1
}

compose() { docker compose -f docker-compose.yml -f "${FRAGMENT}" "$@"; }

detect_mode() {
	if [ -f docker-compose.yml ] && [ -f "${FRAGMENT}" ]; then
		echo compose
	elif [ -d env ] && [ -d sites ]; then
		echo standalone
	else
		echo unknown
	fi
}

install_compose() {
	command -v docker >/dev/null 2>&1 || die "docker not found"
	log "Compose mode: building + starting the wg-agent sidecar"
	compose up -d --build wg-agent
	log "Recreating backend + queue-long with the shared socket/volume mounts"
	compose up -d backend queue-long
	wait_for_socket_compose
	log "Installing ${APP} on site ${SITE}"
	compose exec backend bench --site "${SITE}" install-app "${APP}"
	log "Done (compose): wg-agent is up and ${APP} is installed on ${SITE}."
}

wait_for_socket_compose() {
	log "Waiting for the agent socket at ${SOCKET}"
	for _ in $(seq 1 20); do
		compose exec -T backend test -S "${SOCKET}" >/dev/null 2>&1 && return 0
		sleep 0.5
	done
	die "agent socket ${SOCKET} not ready in backend — check: docker compose logs wg-agent"
}

install_standalone() {
	[ "$(id -u)" -eq 0 ] || die "standalone mode installs a systemd unit — re-run with sudo."
	[ -f "${AGENTD}" ] || die "cannot find agentd at ${AGENTD}"
	command -v python3 >/dev/null 2>&1 || die "python3 not found."
	command -v wg-quick >/dev/null 2>&1 || die "wireguard-tools missing (need wg/wg-quick)."

	local bench_dir bench_user bench_uid
	bench_dir="$(pwd)"
	bench_user="${SUDO_USER:-$(stat -c '%U' env)}"
	bench_uid="$(id -u "${bench_user}")"

	log "Standalone mode: agentd as a systemd unit for ${bench_user} (uid ${bench_uid})"
	install -d -m 0700 -o "${bench_user}" -g "${bench_user}" "${WG_DIR}"
	write_unit "${bench_uid}"

	log "Enabling + starting wg-agent.service"
	systemctl daemon-reload
	systemctl enable --now wg-agent.service
	wait_for_socket

	log "Installing ${APP} on site ${SITE} (as ${bench_user})"
	sudo -u "${bench_user}" bash -c "cd '${bench_dir}' && ./env/bin/bench --site '${SITE}' install-app '${APP}'"
	log "Done (standalone): wg-agent.service is active and ${APP} is installed on ${SITE}."
}

write_unit() {
	cat >/etc/systemd/system/wg-agent.service <<-UNIT
		[Unit]
		Description=vpn_management WireGuard agent (privileged socket)
		After=network-online.target

		[Service]
		Type=simple
		Environment=WG_AGENT_SOCKET_UID=$1
		RuntimeDirectory=wg-agent
		ExecStart=/usr/bin/python3 ${AGENTD}
		Restart=on-failure

		[Install]
		WantedBy=multi-user.target
	UNIT
}

wait_for_socket() {
	for _ in $(seq 1 20); do
		[ -S "${SOCKET}" ] && return 0
		sleep 0.5
	done
	die "agent socket ${SOCKET} never appeared — check: journalctl -u wg-agent.service"
}

main() {
	local mode="${1:-auto}"
	[ "${mode}" = "auto" ] && mode="$(detect_mode)"
	case "${mode}" in
		compose) install_compose ;;
		standalone) install_standalone ;;
		*) die "run from a bench root (compose needs docker-compose.yml; standalone needs env/ + sites/), or pass 'compose'|'standalone'." ;;
	esac
}

main "$@"
