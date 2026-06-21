#!/usr/bin/env bash
# ============================================================================
# vpn_management — easy install
#
# One command turns a fresh Linux server into a working WireGuard control plane:
# an isolated Frappe v16 Docker stack + this app + the privileged wg-agent
# sidecar, with the live wg0 interface provisioned automatically.
#
# Modelled on Frappe's own easy-install (github.com/frappe/bench), but tailored
# to this app: it bakes the app into the image, builds the Vue SPA, wires the
# sidecar, sets the client endpoint, and enables the scheduler — encoding every
# step (and gotcha) from SETTING_UP.md so a user can just "try it".
#
# Usage:
#   ./deploy/easy-install.sh --endpoint <public-ip-or-dns> [options]
#
# Options:
#   --endpoint HOST     Public IP/DNS that clients dial (REQUIRED → vpn_endpoint_host)
#   --project NAME      Compose project / install-dir name (default: vpn-management)
#   --dir PATH          Install directory (default: $HOME/<project>)
#   --site NAME         Frappe site name (default: frontend)
#   --port PORT         Host web port (default: first free from 8080)
#   --frappe-branch B   Frappe branch (default: version-16)
#   --app-source SRC    git URL to clone the app from (default: this checkout)
#   --app-branch B      Branch when --app-source is a git URL (default: version-16)
#   --skip-docker       Do not auto-install Docker
#   -h, --help          Show this help
#
# Run as root on a fresh box, or as a user in the `docker` group.
# ============================================================================
set -euo pipefail

APP="vpn_management"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STACK_DIR="${SCRIPT_DIR}/stack"

PROJECT="vpn-management"
SITE="frontend"
ENDPOINT=""
PORT=""
FRAPPE_BRANCH="version-16"
APP_SOURCE=""
APP_BRANCH="version-16"
INSTALL_DIR=""
SKIP_DOCKER=0

# container frappe uid — bind-mounted ./apps must be writable by it
FRAPPE_UID=1000

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
log()  { printf '\033[92m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[93m[warn]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO="sudo"

usage() { sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

# run docker compose from the install dir → project name == dir basename, which
# is exactly what deploy/install.sh assumes (keeps stack + sidecar in one project)
dc() { (cd "${INSTALL_DIR}" && docker compose "$@"); }
bench() { dc exec -T backend bench --site "${SITE}" "$@"; }
nvm_run() { dc exec -T backend bash -lc "export NVM_DIR=/home/frappe/.nvm; . \$NVM_DIR/nvm.sh; $1"; }

parse_args() {
	while [ $# -gt 0 ]; do
		case "$1" in
			--endpoint) ENDPOINT="$2"; shift 2 ;;
			--project) PROJECT="$2"; shift 2 ;;
			--dir) INSTALL_DIR="$2"; shift 2 ;;
			--site) SITE="$2"; shift 2 ;;
			--port) PORT="$2"; shift 2 ;;
			--frappe-branch) FRAPPE_BRANCH="$2"; shift 2 ;;
			--app-source) APP_SOURCE="$2"; shift 2 ;;
			--app-branch) APP_BRANCH="$2"; shift 2 ;;
			--skip-docker) SKIP_DOCKER=1; shift ;;
			-h|--help) usage 0 ;;
			*) die "unknown option: $1 (see --help)" ;;
		esac
	done
	[ -n "${ENDPOINT}" ] || die "--endpoint <public-ip-or-dns> is required."
	[ -n "${INSTALL_DIR}" ] || INSTALL_DIR="${HOME}/${PROJECT}"
	# compose project name = install dir basename; keep them in sync
	PROJECT="$(basename "${INSTALL_DIR}")"
	PROJECT_NAME_UNDERSCORE="${PROJECT//-/_}"
	IMAGE_NAME="${PROJECT_NAME_UNDERSCORE}:latest"
	BASE_IMAGE="${PROJECT_NAME_UNDERSCORE}-base:latest"
}

# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------
ensure_docker() {
	if command -v docker >/dev/null 2>&1; then
		log "Docker present: $(docker --version)"
	elif [ "${SKIP_DOCKER}" -eq 1 ]; then
		die "Docker not found and --skip-docker set."
	else
		log "Installing Docker via get.docker.com"
		curl -fsSL https://get.docker.com | ${SUDO} sh
		[ "$(id -u)" -eq 0 ] || { ${SUDO} usermod -aG docker "$(id -un)"; warn "Added $(id -un) to the docker group — log out/in if the next step is denied."; }
	fi
	docker compose version >/dev/null 2>&1 || die "Docker Compose v2 plugin not available."
	docker info >/dev/null 2>&1 || die "Cannot talk to the Docker daemon (need root or docker-group membership)."
}

pick_port() {
	[ -n "${PORT}" ] && return 0
	local p listening
	listening="$(ss -tlnH 2>/dev/null | awk '{print $4}' | grep -oE '[0-9]+$' | sort -u || true)"
	for p in $(seq 8080 8200); do
		grep -qx "${p}" <<<"${listening}" || { PORT="${p}"; break; }
	done
	[ -n "${PORT}" ] || die "no free web port found in 8080-8200"
	log "Selected web port ${PORT}"
}

preflight_udp() {
	local used; used="$(ss -ulnH 2>/dev/null | awk '{print $4}' | grep -oE '[0-9]+$' | sort -u || true)"
	grep -qx "44556" <<<"${used}" && warn "UDP 44556 already in use — the default WireGuard listen port may clash." || true
	if command -v wg >/dev/null 2>&1 && ip -br link show type wireguard 2>/dev/null | grep -q '^wg0'; then
		warn "wg0 already exists on this host — installing here may collide with it."
	fi
	return 0
}

prepare_dir() {
	log "Preparing ${INSTALL_DIR}"
	mkdir -p "${INSTALL_DIR}/apps"
	cp "${STACK_DIR}/docker-compose.yml" "${INSTALL_DIR}/docker-compose.yml"
	cp "${STACK_DIR}/Dockerfile"         "${INSTALL_DIR}/Dockerfile"
	cp "${STACK_DIR}/Dockerfile.app"     "${INSTALL_DIR}/Dockerfile.app"
}

fetch_apps() {
	local apps="${INSTALL_DIR}/apps"
	if [ ! -d "${apps}/frappe" ]; then
		log "Cloning Frappe ${FRAPPE_BRANCH}"
		git clone --quiet --branch "${FRAPPE_BRANCH}" --depth 1 https://github.com/frappe/frappe "${apps}/frappe"
	fi
	if [ ! -d "${apps}/${APP}" ]; then
		if [ -n "${APP_SOURCE}" ]; then
			log "Cloning ${APP} from ${APP_SOURCE} (${APP_BRANCH})"
			git clone --quiet --branch "${APP_BRANCH}" "${APP_SOURCE}" "${apps}/${APP}"
		else
			log "Copying ${APP} from ${APP_REPO_DIR}"
			copy_local "${APP_REPO_DIR}/" "${apps}/${APP}/"
		fi
	fi
	# the bench inside the containers runs as uid 1000; it must own ./apps to
	# write node_modules / built assets into the bind-mount
	${SUDO} chown -R "${FRAPPE_UID}:${FRAPPE_UID}" "${apps}"
}

copy_local() {
	local src="$1" dst="$2"
	mkdir -p "${dst}"
	if command -v rsync >/dev/null 2>&1; then
		rsync -a --exclude='frontend/node_modules' --exclude='node_modules' \
			--exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
			--exclude='.ruff_cache' --exclude='.serena' --exclude='.claude' \
			"${src}" "${dst}"
	else
		cp -a "${src}." "${dst}"
		rm -rf "${dst}/.git" "${dst}/frontend/node_modules" "${dst}/node_modules"
		find "${dst}" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	fi
}

write_env() {
	local admin_pw db_pw
	admin_pw="$(openssl rand -hex 12)"
	db_pw="$(openssl rand -hex 12)"
	cat > "${INSTALL_DIR}/.env" <<-EOF
		FRAPPE_VERSION=${FRAPPE_BRANCH}
		SITE_NAME=${SITE}
		ADMIN_PASSWORD=${admin_pw}
		DB_ROOT_PASSWORD=${db_pw}
		MYSQL_ROOT_PASSWORD=${db_pw}
		MARIADB_ROOT_PASSWORD=${db_pw}
		PORT=${PORT}
		PROJECT_NAME=${PROJECT_NAME_UNDERSCORE}
		IMAGE_NAME=${IMAGE_NAME}
		INSTALL_APPS=
	EOF
	cat > "${INSTALL_DIR}/passwords.txt" <<-EOF
		ADMINISTRATOR_PASSWORD=${admin_pw}
		MARIADB_ROOT_PASSWORD=${db_pw}
	EOF
	chmod 600 "${INSTALL_DIR}/passwords.txt"
	log "Generated .env + passwords.txt (Administrator password stored there)"
}

build_images() {
	log "Building base image (${BASE_IMAGE}) — Frappe ${FRAPPE_BRANCH}"
	(cd "${INSTALL_DIR}" && docker build \
		--build-arg "APPS_JSON_BASE64=$(echo '[]' | base64 -w0)" \
		--build-arg "FRAPPE_BRANCH=${FRAPPE_BRANCH}" \
		-t "${BASE_IMAGE}" -f Dockerfile .)
	log "Baking ${APP} into the image (${IMAGE_NAME})"
	(cd "${INSTALL_DIR}" && docker build \
		--build-arg "BASE_IMAGE=${BASE_IMAGE}" \
		-t "${IMAGE_NAME}" -f Dockerfile.app .)
}

start_stack() {
	log "Starting the stack"
	dc up -d
	log "Waiting for site creation (create-site)"
	local state
	for _ in $(seq 1 60); do
		state="$(docker inspect -f '{{.State.Status}}:{{.State.ExitCode}}' "${PROJECT_NAME_UNDERSCORE}_create-site" 2>/dev/null || echo unknown)"
		case "${state}" in
			exited:0) log "Site ${SITE} created"; return ;;
			exited:*) dc logs --tail=20 create-site; die "site creation failed (${state})" ;;
		esac
		sleep 6
	done
	die "site creation timed out"
}

build_assets() {
	log "Installing node deps + building assets (the bind-mount fixes)"
	dc exec -T -u root backend chown -R frappe:frappe sites/assets
	nvm_run "cd apps/frappe && yarn install"
	if [ ! -f "${INSTALL_DIR}/apps/${APP}/${APP}/www/vpn/index.html" ]; then
		log "Building the Vue SPA (frontend assets not prebuilt in this source)"
		nvm_run "cd apps/${APP}/frontend && yarn install && yarn build"
	fi
	nvm_run "cd /home/frappe/frappe-bench && bench build"
	dc restart websocket frontend
}

set_config() {
	log "Setting required site config (endpoint + sync token)"
	bench set-config vpn_endpoint_host "${ENDPOINT}"
	local sync_token; sync_token="$(openssl rand -hex 32)"
	bench set-config vpn_sync_token "${sync_token}"
	echo "VPN_SYNC_TOKEN=${sync_token}" >> "${INSTALL_DIR}/passwords.txt"
}

install_app() {
	log "Installing ${APP} + the wg-agent sidecar (deploy/install.sh compose)"
	(cd "${INSTALL_DIR}" && SITE_NAME="${SITE}" bash "apps/${APP}/deploy/install.sh" compose)
}

enable_scheduler() {
	log "Enabling the scheduler (live handshake/throughput polling)"
	bench scheduler enable
	bench execute vpn_management.tasks.poll_status >/dev/null 2>&1 || true
}

summary() {
	local admin_pw; admin_pw="$(grep ADMINISTRATOR_PASSWORD "${INSTALL_DIR}/passwords.txt" | cut -d= -f2)"
	printf '\n\033[92m========================================================\033[0m\n'
	printf '  vpn_management is up.\n'
	printf '\033[92m========================================================\033[0m\n'
	printf '  Console : http://%s:%s/vpn\n' "${ENDPOINT}" "${PORT}"
	printf '  Desk    : http://%s:%s/app\n' "${ENDPOINT}" "${PORT}"
	printf '  Login   : Administrator / %s\n' "${admin_pw}"
	printf '  Dir     : %s   (run docker compose from here)\n' "${INSTALL_DIR}"
	printf '  Secrets : %s/passwords.txt + sites/%s/site_config.json\n' "${INSTALL_DIR}" "${SITE}"
	printf '\n  Open inbound UDP 44556 on any edge firewall so clients can connect.\n'
	printf '  Put the console behind TLS before exposing the admin login.\n\n'
}

main() {
	parse_args "$@"
	log "Installing ${APP} → project '${PROJECT}' at ${INSTALL_DIR} (endpoint ${ENDPOINT})"
	ensure_docker
	pick_port
	preflight_udp
	prepare_dir
	fetch_apps
	write_env
	build_images
	start_stack
	build_assets
	set_config
	install_app
	enable_scheduler
	summary
}

main "$@"
