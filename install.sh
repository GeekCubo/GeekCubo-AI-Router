#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

HEALTH_TIMEOUT="${GEEKCUBO_INSTALL_HEALTH_TIMEOUT:-120}"
HEALTH_INTERVAL="${GEEKCUBO_INSTALL_HEALTH_INTERVAL:-2}"
OS_RELEASE_FILE="${GEEKCUBO_OS_RELEASE:-/etc/os-release}"
SYSTEMD_DIR="${GEEKCUBO_SYSTEMD_DIR:-/run/systemd/system}"
API_CONTAINER_PORT=8000

DOCKER=()
DOCKER_DISPLAY="docker"
MODE=""
MODE_HOSTNAME=""
ASSUME_YES=0
DRY_RUN=0
CF_TOKEN_FILE=""
MODE_WAS_SAVED=0
PUBLIC_EXPOSE_OPT_IN=0
PORT80_OCCUPIED=0
PORT443_OCCUPIED=0
PORT8787_OCCUPIED=0
PORT_SCAN_AVAILABLE=0
SELINUX_ENFORCING=0
NGINX_LAYOUT=""
NGINX_CONFLICT=0

ok() {
  printf '  ✓ %s\n' "$*"
}

warn() {
  printf '  ! %s\n' "$*" >&2
}

step() {
  printf '\n[%s] %s\n' "$1" "$2"
}

die() {
  printf '\nerror: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Build and start GeekCubo with Docker Compose, wait for the real /health
endpoint, and display the one-time setup token when no administrator exists.

Deployment modes:
  1  Local / Private (default): loopback binding only
  2  VPS + Cloudflare Tunnel (cloudflared connector, token required)
  3  VPS + Nginx + HTTPS (system nginx reverse proxy)
  4  VPS + Caddy + HTTPS (Caddy container with automatic certificates)
  5  VPS without a domain (loopback binding + SSH tunnel)

Options:
  --mode N                    Preselect deployment mode 1-5
  --hostname NAME             Your own public hostname for modes 2-4: a root
                              domain (example.com) or a subdomain
                              (api.example.com); either works
  --yes                       Accept defaults; skip interactive prompts
  --dry-run                   Print the intended host-level changes and exit
                              without mutating anything
  --cloudflare-token-file P   Read the Cloudflare tunnel token from file P
                              (mode 2 only; never pass the token as an argument)
  -h, --help                  Show this help

Environment:
  PUBLIC_BASE_URL                     Your public dashboard URL to display,
                                      e.g. https://example.com
  GEEKCUBO_INSTALL_HEALTH_TIMEOUT     Health-check timeout in seconds (default: 120)
  GEEKCUBO_INSTALL_HEALTH_INTERVAL    Seconds between health checks (default: 2)

Secrets are only accepted through an interactive prompt (read -rs) or through
a file with restrictive permissions. They are never taken from argv, never
written to logs, and never stored in git-tracked files.

Cloudflare Tunnel removal: stop the connector with
  docker compose -f docker-compose.yml -f deploy/cloudflare/docker-compose.cloudflare.yml down
then delete deploy/cloudflare/token. Removing the public hostname route is a
one-time step in the Cloudflare Zero Trust dashboard; this installer never
creates or deletes DNS records.

Rerunning this script is safe. It never deletes the data volume and never
regenerates existing provider credentials, API keys or administrator sessions.
EOF
}

compose() {
  "${DOCKER[@]}" compose "$@"
}

compose_display() {
  printf '%s compose %s' "$DOCKER_DISPLAY" "$*"
}

read_env_var() {
  local key="$1"
  local value="${!key-}"
  if [[ -n "$value" ]]; then
    printf '%s' "$value"
    return 0
  fi
  [[ -f .env ]] || return 0
  value="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)$/\1/p" .env | tail -n 1)"
  value="${value%$'\r'}"
  value="$(printf '%s\n' "$value" | sed -E 's/[[:space:]]+#.*$//')"
  value="$(printf '%s' "$value" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

shape_diagnostics() {
  printf '\nContainer status:\n' >&2
  compose ps >&2 || true
  printf '\nInspect the logs with:\n  %s\n' "$(compose_display logs --tail=100 api)" >&2
  printf 'Logs may contain the one-time setup token. Do not share them.\n' >&2
}

os_id=""
os_version_id=""
os_pretty=""
os_arch=""

detect_os() {
  os_arch="$(uname -m 2>/dev/null || printf 'unknown')"
  if [[ -r "$OS_RELEASE_FILE" ]]; then
    os_id="$(sed -n -E 's/^ID=(.*)$/\1/p' "$OS_RELEASE_FILE" | head -n 1 | tr -d '"')"
    os_version_id="$(sed -n -E 's/^VERSION_ID=(.*)$/\1/p' "$OS_RELEASE_FILE" | head -n 1 | tr -d '"')"
    os_pretty="$(sed -n -E 's/^PRETTY_NAME=(.*)$/\1/p' "$OS_RELEASE_FILE" | head -n 1 | tr -d '"')"
  fi
  if [[ -z "$os_id" ]]; then
    warn "Could not identify this operating system from $OS_RELEASE_FILE."
    warn "GeekCubo officially supports Linux with Docker Engine. Other platforms may work but are untested."
    os_id="unknown"
  fi
  [[ -n "$os_pretty" ]] || os_pretty="$os_id $os_version_id"
  ok "Detected OS: ${os_pretty} (${os_arch})"
}

docker_install_guidance() {
  printf '\nDocker is not installed.\n' >&2
  case "$os_id" in
    ubuntu|debian|raspbian|linuxmint|pop)
      printf 'Suggested installation (Debian/Ubuntu family):\n' >&2
      printf '  sudo apt-get update\n' >&2
      printf '  sudo apt-get install -y docker.io docker-compose-v2\n' >&2
      printf 'or use the official Docker apt repository:\n' >&2
      printf '  https://docs.docker.com/engine/install/%s/\n' "$os_id" >&2
      ;;
    fedora)
      printf 'Suggested installation (Fedora):\n' >&2
      printf '  sudo dnf install -y docker moby-engine docker-compose-plugin\n' >&2
      printf 'Official instructions: https://docs.docker.com/engine/install/fedora/\n' >&2
      ;;
    centos|rhel|rocky|almalinux|ol)
      printf 'Suggested installation (RHEL family):\n' >&2
      printf '  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin\n' >&2
      printf 'Official instructions: https://docs.docker.com/engine/install/centos/\n' >&2
      ;;
    arch|manjaro)
      printf 'Suggested installation (Arch family):\n' >&2
      printf '  sudo pacman -S docker docker-compose\n' >&2
      ;;
    opensuse*|sles)
      printf 'Suggested installation (openSUSE/SLES):\n' >&2
      printf '  sudo zypper install -y docker docker-compose\n' >&2
      ;;
    alpine)
      printf 'Suggested installation (Alpine):\n' >&2
      printf '  apk add docker docker-compose\n' >&2
      ;;
    *)
      printf 'Install Docker Engine with the Compose v2 plugin for your distribution.\n' >&2
      printf 'Official instructions: https://docs.docker.com/engine/install/\n' >&2
      ;;
  esac
  printf 'The installer never installs packages itself. Install Docker, then rerun this script.\n' >&2
  exit 1
}

port_listeners() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null || true
    return 0
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null || true
    return 0
  fi
  return 1
}

port_in_use() {
  local port="$1"
  port_listeners | grep -Eq "[:.]${port}[[:space:]]"
}

detect_ports() {
  if port_listeners >/dev/null 2>&1; then
    PORT_SCAN_AVAILABLE=1
  else
    PORT_SCAN_AVAILABLE=0
    warn "Neither ss nor netstat is available; skipping port conflict detection."
    return 0
  fi
  port_in_use 80 && PORT80_OCCUPIED=1 || true
  port_in_use 443 && PORT443_OCCUPIED=1 || true
  port_in_use 8787 && PORT8787_OCCUPIED=1 || true
}

nginx_present() {
  command -v nginx >/dev/null 2>&1
}

caddy_present() {
  command -v caddy >/dev/null 2>&1
}

systemd_available() {
  [[ -d "$SYSTEMD_DIR" ]] && command -v systemctl >/dev/null 2>&1
}

detect_selinux() {
  SELINUX_ENFORCING=0
  if command -v getenforce >/dev/null 2>&1; then
    if [[ "$(getenforce 2>/dev/null)" == "Enforcing" ]]; then
      SELINUX_ENFORCING=1
    fi
  fi
}

detect_firewall() {
  local found=0
  if command -v ufw >/dev/null 2>&1; then
    found=1
    local ufw_status
    ufw_status="$(ufw status 2>/dev/null | head -n 1 || true)"
    printf '  ufw: %s\n' "${ufw_status:-unknown}"
  fi
  if command -v firewall-cmd >/dev/null 2>&1; then
    found=1
    local fw_state
    fw_state="$(firewall-cmd --state 2>/dev/null || printf 'not running')"
    printf '  firewalld: %s\n' "$fw_state"
  fi
  if (( found == 0 )); then
    printf '  No ufw/firewalld firewall detected on this host.\n'
  fi
}

firewall_report() {
  local needs=0
  case "$MODE" in
    2)
      needs=0
      ;;
    3|4)
      needs=1
      ;;
  esac
  if (( needs == 1 )); then
    printf 'This mode requires inbound TCP 80 and 443 open.\n'
    printf 'The installer never opens ports automatically. If a firewall is active, allow them, e.g.:\n'
    printf '  ufw allow 80/tcp && ufw allow 443/tcp\n'
    printf '  firewall-cmd --permanent --add-service=http --add-service=https && firewall-cmd --reload\n'
    printf 'Also check provider security groups / network ACLs.\n'
    printf 'Note: Docker manages its own iptables rules and can bypass ufw for published container ports.\n'
  fi
}

save_mode() {
  mkdir -p deploy
  local tmp
  tmp="$(mktemp deploy/.mode.XXXXXX)"
  chmod 600 "$tmp"
  {
    printf 'MODE=%s\n' "$MODE"
    printf 'HOSTNAME=%s\n' "$MODE_HOSTNAME"
  } >"$tmp"
  mv "$tmp" deploy/.mode
}

load_mode() {
  [[ -f deploy/.mode ]] || return 0
  local saved
  saved="$(sed -n -E 's/^MODE=(.*)$/\1/p' deploy/.mode | head -n 1)"
  if [[ -z "$MODE" && "$saved" =~ ^[1-5]$ ]]; then
    MODE="$saved"
    MODE_WAS_SAVED=1
  fi
  if [[ -z "$MODE_HOSTNAME" ]]; then
    MODE_HOSTNAME="$(sed -n -E 's/^HOSTNAME=(.*)$/\1/p' deploy/.mode | head -n 1)"
  fi
}

interactive_ok() {
  [[ -t 0 && "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 ]]
}

choose_mode() {
  if [[ -n "$MODE" ]]; then
    [[ "$MODE" =~ ^[1-5]$ ]] || die "--mode must be a number between 1 and 5."
    return 0
  fi
  if interactive_ok; then
    printf '\nChoose a deployment mode:\n'
    printf '  1) Local / Private (default)\n'
    printf '  2) VPS + Cloudflare Tunnel\n'
    printf '  3) VPS + Nginx + HTTPS\n'
    printf '  4) VPS + Caddy + HTTPS\n'
    printf '  5) VPS without a domain\n'
    local answer
    read -r -p "Mode [1]: " answer
    MODE="${answer:-1}"
    [[ "$MODE" =~ ^[1-5]$ ]] || die "Invalid mode: $MODE"
  else
    MODE="1"
  fi
}

prompt_hostname() {
  if [[ -n "$MODE_HOSTNAME" ]]; then
    return 0
  fi
  if interactive_ok; then
    read -r -p "Your public hostname (e.g. example.com or api.example.com): " MODE_HOSTNAME
  fi
  [[ -n "$MODE_HOSTNAME" ]] || die "Mode $MODE requires a hostname. Pass --hostname or run interactively."
  if [[ ! "$MODE_HOSTNAME" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]]; then
    die "Invalid hostname: $MODE_HOSTNAME"
  fi
}

validate_secret_file() {
  local path="$1"
  [[ -f "$path" ]] || die "Secret file not found: $path"
  [[ -s "$path" ]] || die "Secret file is empty: $path"
  local perms
  perms="$(stat -c '%a' "$path" 2>/dev/null || stat -f '%Lp' "$path" 2>/dev/null || printf '')"
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    die "Secret file $path has permissions $perms. Run: chmod 600 $path"
  fi
}

cloudflare_prepare() {
  mkdir -p deploy/cloudflare
  local token_target="deploy/cloudflare/token"
  local have_token=0
  if [[ -n "$CF_TOKEN_FILE" ]]; then
    validate_secret_file "$CF_TOKEN_FILE"
    have_token=1
  elif [[ -f "$token_target" ]]; then
    validate_secret_file "$token_target"
    have_token=1
  elif interactive_ok; then
    printf 'Paste the Cloudflare tunnel token (input hidden). Create it in the\n'
    printf 'Zero Trust dashboard under Networks -> Tunnels; it is shown once.\n'
    local token=""
    read -r -s -p "Tunnel token: " token
    printf '\n'
    if [[ -n "$token" ]]; then
      umask 077
      printf '%s' "$token" >"$token_target"
      chmod 600 "$token_target"
      token=""
      have_token=1
    fi
  fi
  if (( have_token == 0 )); then
    die "Mode 2 requires a tunnel token. Provide --cloudflare-token-file PATH, place a chmod-600 file at $token_target, or run interactively."
  fi
  if [[ -n "$CF_TOKEN_FILE" ]]; then
    umask 077
    cp "$CF_TOKEN_FILE" "$token_target"
    chmod 600 "$token_target"
  fi
  cat >deploy/cloudflare/docker-compose.cloudflare.yml <<'EOF'
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    profiles: ["cloudflare"]
    secrets:
      - cloudflare_tunnel_token
    entrypoint: ["/bin/sh", "-c"]
    command:
      - "cloudflared tunnel --no-autoupdate run --token \"$$(cat /run/secrets/cloudflare_tunnel_token)\""
    depends_on:
      - api

secrets:
  cloudflare_tunnel_token:
    file: ./token
EOF
  ok "Wrote deploy/cloudflare/docker-compose.cloudflare.yml (cloudflared reads the token only from the mounted file)"
  printf 'One-time dashboard step: in the Cloudflare Zero Trust tunnel page, add a\n'
  printf 'public hostname route: %s -> http://api:8000\n' "${MODE_HOSTNAME:-<your hostname>}"
  printf 'This installer never creates or deletes DNS records.\n'
  printf 'Note: connector health (cloudflared running) is not the same as verified\n'
  printf 'public HTTPS. Verify https://%s manually after the route exists.\n' "${MODE_HOSTNAME:-<your hostname>}"
}

nginx_detect_layout() {
  NGINX_LAYOUT=""
  local dump
  dump="$(nginx -T 2>/dev/null || true)"
  [[ -n "$dump" ]] || return 0
  if grep -q 'sites-enabled' <<<"$dump"; then
    NGINX_LAYOUT="debian"
  elif grep -q 'conf.d/' <<<"$dump"; then
    NGINX_LAYOUT="confd"
  fi
}

nginx_check_conflict() {
  NGINX_CONFLICT=0
  local dump
  dump="$(nginx -T 2>/dev/null || true)"
  [[ -n "$dump" && -n "$MODE_HOSTNAME" ]] || return 0
  if grep -E '^[[:space:]]*server_name[[:space:]]' <<<"$dump" | grep -qw "$MODE_HOSTNAME"; then
    NGINX_CONFLICT=1
  fi
  if [[ -n "${GEEKCUBO_FAKE_NGINX_CONFLICT:-}" ]]; then
    NGINX_CONFLICT=1
  fi
}

# Request-body ceiling for the generated vhost. nginx defaults to 1 MB, which
# would reject chat attachments (ATTACHMENT_MAX_MB, default 25, hard ceiling
# 200) with 413 before they reach the app. Derive the limit from the
# configured attachment size plus multipart/form overhead headroom.
nginx_body_limit_mb() {
  local mb
  mb="$(read_env_var ATTACHMENT_MAX_MB)"
  [[ "$mb" =~ ^[0-9]+$ ]] || mb=25
  (( mb < 1 )) && mb=1
  (( mb > 200 )) && mb=200
  printf '%s' "$(( mb + 7 ))"
}

nginx_write_vhost() {
  local body_limit_mb
  body_limit_mb="$(nginx_body_limit_mb)"
  mkdir -p deploy/nginx
  cat >deploy/nginx/geekcubo.conf <<EOF
# Managed by the GeekCubo installer. Safe to regenerate by rerunning ./install.sh.
#
# This file is included from nginx's http context (sites-enabled / conf.d), so
# the map below is valid here. The map is what makes the WebSocket upgrade
# used by Local AI Connect (/api/local-connect/agent) work: without it
# \$geekcubo_connection_upgrade would be an unknown variable and nginx -t
# would fail. A unique variable name avoids clashing with a \$connection_upgrade
# map another vhost may already define.
map \$http_upgrade \$geekcubo_connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name ${MODE_HOSTNAME};

    # Chat attachments are limited by ATTACHMENT_MAX_MB in the app; this keeps
    # the proxy from rejecting them first (nginx's default is 1 MB).
    client_max_body_size ${body_limit_mb}m;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$geekcubo_connection_upgrade;
        # Long timeouts keep idle connector sockets and long-lived streams open.
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF
  ok "Wrote deploy/nginx/geekcubo.conf"
}

nginx_install_vhost() {
  local target_dir=""
  case "$NGINX_LAYOUT" in
    debian) target_dir="/etc/nginx/sites-available" ;;
    confd) target_dir="/etc/nginx/conf.d" ;;
  esac
  if [[ -z "$target_dir" || ! -d "$target_dir" ]]; then
    warn "Could not determine the nginx include layout safely."
    nginx_manual_instructions
    return 0
  fi
  local target="$target_dir/geekcubo.conf"
  if [[ ! -w "$target_dir" ]]; then
    warn "$target_dir is not writable by this user."
    nginx_manual_instructions
    return 0
  fi
  if [[ -f "$target" ]]; then
    if grep -q 'Managed by the GeekCubo installer' "$target" 2>/dev/null; then
      cp "$target" "${target}.bak.$(date +%Y%m%d%H%M%S)"
      ok "Backed up the existing installer-owned file"
    else
      warn "$target exists and is not managed by this installer; refusing to overwrite it."
      nginx_manual_instructions
      return 0
    fi
  fi
  cp deploy/nginx/geekcubo.conf "$target"
  if [[ "$NGINX_LAYOUT" == "debian" ]]; then
    ln -sfn "$target" /etc/nginx/sites-enabled/geekcubo.conf
  fi
  if ! nginx -t >/dev/null 2>&1; then
    warn "nginx -t failed; rolling back the installer-owned file."
    rm -f "$target"
    [[ "$NGINX_LAYOUT" == "debian" ]] && rm -f /etc/nginx/sites-enabled/geekcubo.conf
    local latest
    latest="$(ls -1t "${target}".bak.* 2>/dev/null | head -n 1 || true)"
    if [[ -n "$latest" ]]; then
      cp "$latest" "$target"
      [[ "$NGINX_LAYOUT" == "debian" ]] && ln -sfn "$target" /etc/nginx/sites-enabled/geekcubo.conf
    fi
    nginx_manual_instructions
    return 0
  fi
  if command -v systemctl >/dev/null 2>&1 && systemd_available; then
    systemctl reload nginx 2>/dev/null && ok "Reloaded nginx" || warn "nginx reload failed; run: sudo systemctl reload nginx"
  else
    nginx -s reload >/dev/null 2>&1 && ok "Reloaded nginx" || warn "Could not reload nginx automatically; run: sudo nginx -s reload"
  fi
  printf 'HTTPS: obtain a certificate with certbot, e.g.:\n'
  printf '  sudo certbot --nginx -d %s\n' "$MODE_HOSTNAME"
  printf 'Then set PUBLIC_BASE_URL=https://%s and TRUST_PROXY_HEADERS=true in .env.\n' "$MODE_HOSTNAME"
}

nginx_manual_instructions() {
  printf 'Manual nginx setup:\n' >&2
  printf '  1. Review deploy/nginx/geekcubo.conf in this repository.\n' >&2
  printf '  2. Copy it into your nginx include directory (Debian: /etc/nginx/sites-available\n' >&2
  printf '     plus a symlink in sites-enabled; RHEL: /etc/nginx/conf.d).\n' >&2
  printf '  3. Validate with: sudo nginx -t\n' >&2
  printf '  4. Reload with: sudo systemctl reload nginx\n' >&2
  printf 'The installer never touches /etc/nginx/nginx.conf or unrelated virtual hosts.\n' >&2
}

selinux_nginx_guidance() {
  (( SELINUX_ENFORCING == 1 )) || return 0
  warn "SELinux is in Enforcing mode."
  printf 'Nginx needs the narrowly scoped boolean httpd_can_network_connect to proxy\n' >&2
  printf 'to 127.0.0.1:8787. The installer never disables SELinux.\n' >&2
  local approved=0
  if interactive_ok; then
    local answer
    read -r -p "Run 'sudo setsebool -P httpd_can_network_connect 1' now? [y/N]: " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] && approved=1
  fi
  if (( approved == 1 )); then
    if sudo -n setsebool -P httpd_can_network_connect 1 2>/dev/null; then
      ok "Enabled httpd_can_network_connect"
    else
      warn "setsebool failed; run it manually: sudo setsebool -P httpd_can_network_connect 1"
    fi
  else
    printf 'Skipped. To allow the proxy manually, run:\n'
    printf '  sudo setsebool -P httpd_can_network_connect 1\n'
  fi
}

caddy_prepare() {
  prompt_hostname
  mkdir -p deploy/caddy
  cat >deploy/caddy/Caddyfile <<EOF
${MODE_HOSTNAME} {
	reverse_proxy 127.0.0.1:8787
}
EOF
  cat >deploy/caddy/docker-compose.caddy.yml <<'EOF'
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    profiles: ["caddy"]
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      - api

volumes:
  caddy-data:
  caddy-config:
EOF
  ok "Wrote deploy/caddy/Caddyfile and deploy/caddy/docker-compose.caddy.yml"
  printf 'Certificates are stored persistently in the caddy-data volume.\n'
  printf 'The GeekCubo backend stays bound to loopback; only Caddy listens publicly.\n'
}

caddy_check_ports() {
  (( PORT_SCAN_AVAILABLE == 1 )) || return 0
  if (( PORT80_OCCUPIED == 1 || PORT443_OCCUPIED == 1 )); then
    printf '\nPorts 80 and/or 443 already have a listener on this host.\n' >&2
    printf 'Refusing to silently compete with an existing proxy or web server.\n' >&2
    printf 'Stop the conflicting service, or pick another mode (e.g. --mode 2 or --mode 3).\n' >&2
    exit 1
  fi
}

private_vps_notes() {
  printf 'Private VPS mode: the dashboard stays bound to loopback only.\n'
  printf 'Reach it through an SSH tunnel:\n'
  printf '  ssh -L 8787:127.0.0.1:8787 <user>@<server>\n'
  local expose=0
  if (( PUBLIC_EXPOSE_OPT_IN == 1 )); then
    expose=1
  elif interactive_ok; then
    local answer
    read -r -p "Expose port 8787 publicly without HTTPS (NOT recommended)? [y/N]: " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] && expose=1
  fi
  if (( expose == 1 )); then
    warn "Public exposure without TLS means credentials and tokens travel unencrypted."
    warn "Edit docker-compose.yml's port binding yourself; the installer never enables this by default."
    printf 'Strongly consider mode 2, 3 or 4 instead.\n'
  else
    ok "Keeping loopback-only binding"
  fi
}

dry_run_report() {
  printf '\n--dry-run: planned host-level changes (nothing was modified)\n'
  printf '  Mode: %s\n' "${MODE:-1}"
  [[ -n "$MODE_HOSTNAME" ]] && printf '  Hostname: %s\n' "$MODE_HOSTNAME"
  printf '  OS: %s (%s)\n' "${os_pretty:-unknown}" "$os_arch"
  printf '  - Would ensure .env exists (created from .env.example only if missing)\n'
  printf '  - Would run: %s\n' "$(compose_display up -d --build)"
  printf '  - Would poll http://127.0.0.1:8000/health inside the api container\n'
  printf '  - Would run python -m app.admin_cli status and show a setup token only if NOT INITIALIZED\n'
  printf '  - Would persist the selected mode in deploy/.mode (chmod 600, gitignored)\n'
  case "$MODE" in
    2)
      printf '  - Would write deploy/cloudflare/token (chmod 600) from a prompt or --cloudflare-token-file\n'
      printf '  - Would write deploy/cloudflare/docker-compose.cloudflare.yml\n'
      printf '  - Would start cloudflared via the cloudflare compose profile\n'
      printf '  - No DNS records would be created; the public hostname route is a manual dashboard step\n'
      ;;
    3)
      printf '  - Would write deploy/nginx/geekcubo.conf\n'
      if nginx_present; then
        printf '  - nginx detected; would attempt install into the detected include layout with backup + rollback\n'
      else
        printf '  - nginx not detected; would print manual installation instructions only\n'
      fi
      printf '  - Would check for a conflicting server_name and refuse to touch other vhosts\n'
      ;;
    4)
      printf '  - Would write deploy/caddy/Caddyfile and deploy/caddy/docker-compose.caddy.yml\n'
      printf '  - Would refuse to start if ports 80/443 are already occupied\n'
      ;;
    5)
      printf '  - Would keep loopback-only binding and print an SSH tunnel template\n'
      ;;
  esac
  printf '\nNo secrets were read or printed during this dry run.\n'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --hostname)
      MODE_HOSTNAME="${2:-}"
      shift 2
      ;;
    --yes|-y)
      ASSUME_YES=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --cloudflare-token-file)
      CF_TOKEN_FILE="${2:-}"
      shift 2
      ;;
    --expose-public)
      PUBLIC_EXPOSE_OPT_IN=1
      shift
      ;;
    *)
      die "unknown argument: $1 (try --help)"
      ;;
  esac
done

[[ "$HEALTH_TIMEOUT" =~ ^[0-9]+$ ]] || die "GEEKCUBO_INSTALL_HEALTH_TIMEOUT must be a whole number of seconds."
[[ "$HEALTH_INTERVAL" =~ ^[0-9]+$ ]] || die "GEEKCUBO_INSTALL_HEALTH_INTERVAL must be a whole number of seconds."

printf 'GeekCubo installer\n'

step 0/6 "Detecting the environment"
detect_os
detect_ports
detect_selinux
load_mode
choose_mode
case "$MODE" in
  2|3|4) prompt_hostname ;;
esac
if (( MODE_WAS_SAVED == 1 )); then
  ok "Reusing the previously selected mode $MODE (deploy/.mode)"
fi
if command -v systemctl >/dev/null 2>&1 && systemd_available; then
  ok "systemd is available"
else
  warn "systemd not detected; service management instructions may differ."
fi
if nginx_present; then
  ok "nginx is installed"
fi
if caddy_present; then
  ok "caddy is installed"
fi
if (( PORT8787_OCCUPIED == 1 )); then
  warn "Port 8787 already has a listener. If this is not GeekCubo, the health check may fail."
fi
if [[ "$MODE" == "3" || "$MODE" == "4" ]]; then
  printf '\nFirewall status (read-only):\n'
  detect_firewall
fi

if (( DRY_RUN == 1 )); then
  dry_run_report
  exit 0
fi

case "$MODE" in
  2)
    step "2a" "Preparing Cloudflare Tunnel"
    cloudflare_prepare
    ;;
  3)
    step "2a" "Preparing the nginx virtual host"
    prompt_hostname
    nginx_write_vhost
    if nginx_present; then
      nginx_detect_layout
      nginx_check_conflict
      if (( NGINX_CONFLICT == 1 )); then
        die "An existing nginx server block already claims server_name $MODE_HOSTNAME. Resolve it manually; the installer never touches unrelated vhosts."
      fi
      nginx_install_vhost
      selinux_nginx_guidance
    else
      warn "nginx is not installed."
      nginx_manual_instructions
    fi
    ;;
  4)
    step "2a" "Preparing Caddy"
    caddy_check_ports
    caddy_prepare
    ;;
  5)
    step "2a" "Configuring private VPS access"
    private_vps_notes
    ;;
esac

save_mode

step 1/6 "Checking Docker"
command -v docker >/dev/null 2>&1 || docker_install_guidance

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
  DOCKER_DISPLAY="docker"
  ok "Docker Engine is reachable"
elif command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
  DOCKER_DISPLAY="sudo docker"
  ok "Docker Engine is reachable through sudo"
else
  die "Docker is installed but the current user cannot reach the daemon. Start Docker, add your user to the docker group, or rerun with sudo."
fi

if ! compose version >/dev/null 2>&1; then
  die "Docker Compose v2 is required. Install the Compose plugin, then rerun this script."
fi
ok "Docker Compose v2 is available"

step 2/6 "Checking configuration"
[[ -f docker-compose.yml ]] || die "docker-compose.yml is missing. Run this script from the GeekCubo repository root."

if [[ ! -f .env ]]; then
  [[ -f .env.example ]] || die ".env and .env.example are both missing; cannot create configuration."
  cp .env.example .env
  ok "Created .env from .env.example"
else
  ok "Using existing .env (not modified)"
fi

if ! compose config >/dev/null; then
  die "docker compose config rejected the configuration. Check .env and docker-compose.yml."
fi
ok "Compose configuration is valid"

COMPOSE_FILES=()
case "$MODE" in
  2)
    COMPOSE_FILES=(-f docker-compose.yml -f deploy/cloudflare/docker-compose.cloudflare.yml)
    ;;
  4)
    COMPOSE_FILES=(-f docker-compose.yml -f deploy/caddy/docker-compose.caddy.yml)
    ;;
esac

COMPOSE_PROFILES=()
case "$MODE" in
  2) COMPOSE_PROFILES+=(cloudflare) ;;
  4) COMPOSE_PROFILES+=(caddy) ;;
esac
SEARCH_PROFILE=""
SEARCH_CHOICE="skip"
SEARCH_EXISTING_URL=""
SEARCH_BRAVE_KEY=""
SEARCH_TAVILY_KEY=""

prompt_web_search() {
  if [[ -n "${GEEKCUBO_SEARCH_BACKEND:-}" ]]; then
    case "$GEEKCUBO_SEARCH_BACKEND" in
      skip|none) SEARCH_CHOICE="skip" ;;
      searxng) SEARCH_CHOICE="searxng" ;;
      existing)
        SEARCH_CHOICE="existing"
        SEARCH_EXISTING_URL="${GEEKCUBO_SEARXNG_URL:-}"
        ;;
      brave)
        SEARCH_CHOICE="brave"
        SEARCH_BRAVE_KEY="${GEEKCUBO_BRAVE_KEY:-}"
        ;;
      tavily)
        SEARCH_CHOICE="tavily"
        SEARCH_TAVILY_KEY="${GEEKCUBO_TAVILY_KEY:-}"
        ;;
      *) SEARCH_CHOICE="skip" ;;
    esac
    return 0
  fi
  if ! interactive_ok; then
    SEARCH_CHOICE="skip"
    return 0
  fi
  printf '\nOptional: configure native-Chat web search?\n'
  printf '  1) Not now (default)\n'
  printf '  2) Install a private SearXNG instance (Docker, "search" profile)\n'
  printf '  3) Connect an existing SearXNG instance\n'
  printf '  4) Brave Search API\n'
  printf '  5) Tavily API\n'
  local answer
  read -r -p "Web search [1]: " answer
  case "${answer:-1}" in
    2) SEARCH_CHOICE="searxng" ;;
    3) SEARCH_CHOICE="existing" ;;
    4) SEARCH_CHOICE="brave" ;;
    5) SEARCH_CHOICE="tavily" ;;
    *) SEARCH_CHOICE="skip" ;;
  esac
}

apply_web_search_choice() {
  case "$SEARCH_CHOICE" in
    searxng)
      SEARCH_PROFILE="search"
      if [[ -z "$(read_env_var SEARXNG_SECRET)" ]]; then
        printf 'SEARXNG_SECRET=%s\n' "$(openssl rand -hex 32)" >> .env
      fi
      printf '  Web search: private SearXNG will start alongside the api container.\n'
      ;;
    existing)
      if [[ -z "$SEARCH_EXISTING_URL" ]] && interactive_ok; then
        read -r -p "Existing SearXNG URL (e.g. http://searxng.internal:8080): " SEARCH_EXISTING_URL
      fi
      if [[ -z "$SEARCH_EXISTING_URL" ]]; then
        warn "No SearXNG URL provided; skipping web search configuration."
        SEARCH_CHOICE="skip"
        return 0
      fi
      printf '  Web search: existing SearXNG at %s\n' "$SEARCH_EXISTING_URL"
      printf '  Configure it in the dashboard under Settings → Chat → Web Search.\n'
      ;;
    brave)
      if [[ -z "$SEARCH_BRAVE_KEY" ]] && interactive_ok; then
        local key=""
        read -r -s -p "Brave Search API key (input hidden): " key
        printf '\n'
        SEARCH_BRAVE_KEY="$key"
      fi
      if [[ -z "$SEARCH_BRAVE_KEY" ]]; then
        warn "No Brave API key provided; skipping web search configuration."
        SEARCH_CHOICE="skip"
        return 0
      fi
      printf '  Web search: Brave Search API key will be stored via the dashboard.\n'
      printf '  Complete setup in Settings → Chat → Web Search after first login.\n'
      ;;
    tavily)
      if [[ -z "$SEARCH_TAVILY_KEY" ]] && interactive_ok; then
        local key=""
        read -r -s -p "Tavily API key (input hidden): " key
        printf '\n'
        SEARCH_TAVILY_KEY="$key"
      fi
      if [[ -z "$SEARCH_TAVILY_KEY" ]]; then
        warn "No Tavily API key provided; skipping web search configuration."
        SEARCH_CHOICE="skip"
        return 0
      fi
      printf '  Web search: Tavily API key will be stored via the dashboard.\n'
      printf '  Complete setup in Settings → Chat → Web Search after first login.\n'
      ;;
    *)
      printf '  Web search skipped. Enable later by re-running ./install.sh or:\n'
      printf '    docker compose --profile search up -d\n'
      ;;
  esac
}

prompt_web_search
apply_web_search_choice

step 3/6 "Starting GeekCubo"
printf '  Building and starting the container; first run can take a few minutes.\n'
if [[ -n "$SEARCH_PROFILE" ]]; then
  COMPOSE_PROFILES+=("$SEARCH_PROFILE")
fi
PROFILE_ARGS=()
for profile in "${COMPOSE_PROFILES[@]}"; do
  PROFILE_ARGS+=(--profile "$profile")
done
compose "${PROFILE_ARGS[@]}" "${COMPOSE_FILES[@]}" up -d --build || die "docker compose up failed."
ok "Container started"

step 4/6 "Waiting for the application health check"
deadline=$((SECONDS + HEALTH_TIMEOUT))
healthy=0
while (( SECONDS < deadline )); do
  if compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep "$HEALTH_INTERVAL"
done

if (( healthy == 0 )); then
  printf '\nHealth check did not pass within %ss.\n' "$HEALTH_TIMEOUT" >&2
  shape_diagnostics
  exit 1
fi
ok "Application is healthy"

step 5/6 "Checking administrator setup"
if ! status_output="$(compose exec -T api python -m app.admin_cli status 2>&1)"; then
  printf '\nCould not read administrator status.\n' >&2
  printf '%s\n' "$status_output" >&2
  shape_diagnostics
  exit 1
fi

initialized=1
if [[ "$status_output" == *"NOT INITIALIZED"* ]]; then
  initialized=0
fi

if (( initialized == 0 )); then
  ok "Administrator setup is pending"
else
  ok "Administrator already configured"
fi

step 6/6 "Finishing setup"
public_url="$(read_env_var PUBLIC_BASE_URL)"
if [[ -n "$public_url" ]]; then
  if [[ ! "$public_url" =~ ^https?://[^[:space:]]+$ ]]; then
    die "PUBLIC_BASE_URL must start with http:// or https:// and contain no spaces."
  fi
  public_url="${public_url%/}"
fi

bind="$(compose port api "$API_CONTAINER_PORT" 2>/dev/null | head -n 1 || true)"
local_port="8787"
if [[ "$bind" == *:* ]]; then
  local_port="${bind##*:}"
fi
local_url="http://127.0.0.1:${local_port}"
bind_host="${bind%:*}"
loopback=0
case "$bind_host" in
  127.0.0.1|localhost|"[::1]")
    loopback=1
    ;;
esac

setup_token_block=""
if (( initialized == 0 )); then
  if token_output="$(compose exec -T api python -m app.admin_cli setup-token 2>&1)"; then
    setup_token_block="$token_output"
  elif compose exec -T api python -m app.admin_cli status 2>/dev/null | grep -q "NOT INITIALIZED"; then
    printf '\nCould not issue the administrator setup token.\n' >&2
    printf '%s\n' "$token_output" >&2
    printf 'Retry with:\n  %s\n' "$(compose_display exec -T api python -m app.admin_cli setup-token)" >&2
    shape_diagnostics
    exit 1
  else
    initialized=1
    ok "Administrator was configured while the installer was running"
  fi
fi

printf '\n────────────────────────────────────────────────────────────\n'
printf 'GeekCubo is running.\n\n'

if [[ -n "$public_url" ]]; then
  printf 'Dashboard: %s\n' "$public_url"
  printf 'Reverse proxy target: %s\n' "$local_url"
  if [[ "$public_url" == http://* ]]; then
    warn "PUBLIC_BASE_URL uses plain HTTP. Use HTTPS and set TRUST_PROXY_HEADERS=true in .env."
  else
    printf 'Set TRUST_PROXY_HEADERS=true in .env when TLS terminates at your proxy.\n'
  fi
elif (( loopback == 1 )); then
  printf 'Dashboard: %s\n' "$local_url"
  printf 'The port is bound to loopback only. For remote access, use an SSH tunnel:\n'
  printf '  ssh -L %s:127.0.0.1:%s <user>@<server>\n' "$local_port" "$local_port"
  printf 'or put a TLS reverse proxy in front of it. Do not expose the admin port directly.\n'
else
  printf 'Dashboard (local): %s\n' "$local_url"
  printf 'The container is published on %s. Use your server address or, preferably, a TLS reverse proxy.\n' "${bind:-another host interface}"
  printf 'Do not expose the administrator port directly to the internet.\n'
fi

case "$MODE" in
  2)
    printf '\nCloudflare Tunnel: the connector runs via the cloudflare compose profile.\n'
    printf 'Verify the public route manually: https://%s\n' "${MODE_HOSTNAME:-<your hostname>}"
    printf 'To disconnect: docker compose -f docker-compose.yml -f deploy/cloudflare/docker-compose.cloudflare.yml down\n'
    printf 'then delete deploy/cloudflare/token. Remove the public hostname in the dashboard.\n'
    ;;
  3)
    printf '\nNginx mode: virtual host source kept at deploy/nginx/geekcubo.conf.\n'
    printf 'Finish HTTPS with: sudo certbot --nginx -d %s\n' "$MODE_HOSTNAME"
    ;;
  4)
    printf '\nCaddy mode: HTTPS is issued automatically for %s.\n' "$MODE_HOSTNAME"
    printf 'Set PUBLIC_BASE_URL=https://%s and TRUST_PROXY_HEADERS=true in .env.\n' "$MODE_HOSTNAME"
    ;;
  5)
    printf '\nPrivate VPS: use the SSH tunnel shown above. No ports were opened.\n'
    ;;
esac

if [[ -n "$setup_token_block" ]]; then
  printf '\nAdministrator setup token:\n'
  printf '%s\n' "$setup_token_block" | sed 's/^/  /'
  printf '\nOpen the dashboard and choose “Create Administrator Account”.\n'
  printf 'Treat this token like a password. It is invalidated after setup; do not share screenshots or logs containing it.\n'
else
  printf '\nAn administrator already exists, so no setup token was generated or displayed.\n'
  printf 'Sign in with your existing credentials.\n'
fi

printf '\nNext: create an sk-geek-* API key under Settings → API Keys.\n'
printf '\nUseful commands:\n'
printf '  %s\n' "$(compose_display ps)"
printf '  %s\n' "$(compose_display logs --tail=100 api)"
printf '\nRerunning ./install.sh is safe: it preserves the data volume, .env, administrator,\n'
printf 'provider credentials, encryption secrets and API keys.\n'
printf '\nTo add or remove web search later without reinstalling:\n'
printf '  Enable : docker compose --profile search up -d\n'
printf '  Disable: docker compose --profile search down\n'
printf 'Or rerun ./install.sh and answer the web-search prompt again.\n'
