#!/usr/bin/env bash
#
#  Shorts Hub — one-command installer for Proxmox LXC/VM (or any Debian/Ubuntu host)
#
#  Run directly with curl:
#      curl -fsSL https://raw.githubusercontent.com/Xznder1984/Shorts-Hub/main/deploy/install.sh | bash
#
#  This script:
#    1. Checks for git + docker + docker compose
#    2. Offers to install missing dependencies (apt)
#    3. Clones (or updates) the repo to ~/shorts-hub
#    4. Creates .env from .env.example if missing (you edit to add API keys)
#    5. Runs docker compose up -d --build
#    6. Prints next steps (DNS, port forwarding, Caddy domain)
#
#  Safe to re-run: it's idempotent.
# ==============================================================================

set -euo pipefail

REPO_URL="https://github.com/Xznder1984/Shorts-Hub.git"
INSTALL_URL="https://raw.githubusercontent.com/Xznder1984/Shorts-Hub/main/deploy/install.sh"
INSTALL_DIR="${SHORTS_HUB_DIR:-$HOME/shorts-hub}"
DOMAIN="${SHORTS_HUB_DOMAIN:-shortshub.example.com}"
NO_INSTALL_DEPS="${NO_INSTALL_DEPS:-0}"

c_red=$'\033[0;31m'; c_green=$'\033[0;32m'; c_yellow=$'\033[1;33m'
c_cyan=$'\033[0;36m'; c_bold=$'\033[1m'; c_reset=$'\033[0m'

info()  { printf "%s[*]%s %s\n" "$c_cyan" "$c_reset" "$*"; }
ok()    { printf "%s[OK]%s %s\n" "$c_green" "$c_reset" "$*"; }
warn()  { printf "%s[!]%s %s\n" "$c_yellow" "$c_reset" "$*"; }
fail()  { printf "%s[ERR]%s %s\n" "$c_red" "$c_reset" "$*"; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1; }

# Safe prompts that never abort under `set -e` — critical for the
# `curl ... | bash` flow, where stdin is EOF and `read` returns non-zero.
is_interactive() { [[ -t 0 ]]; }

ask_yn() {
  if ! is_interactive; then return 1; fi
  local ans
  read -rp "$1" ans || return 1
  [[ "$ans" =~ ^[Yy]$ ]]
}

ask_value() {
  if ! is_interactive; then echo ""; return 0; fi
  local ans
  read -rp "$1" ans || ans=""
  printf '%s' "$ans"
}

# ---------------------------------------------------------------------------
banner() {
  cat <<EOF
${c_bold}${c_cyan}
   ____  _                 _     _   _                _
  / ___|| |__   ___  _ __ | |_  | | | |__   ___ _   _| |__
  \___ \| '_ \ / _ \| '_ \| __| | | | '_ \ / __| | | | '_ \
   ___) | | | | (_) | | | | |_  | |_| | | | (__| |_| | |_) |
  |____/|_| |_|\___/|_| |_|\__|  \___/|_|_|\___|\__,_|_.__/

  TikTok / Reels / YouTube Shorts in one feed
  Installer for Proxmox LXC / VM (Debian/Ubuntu)
${c_reset}
EOF
}

check_deps() {
  info "Checking dependencies..."

  local missing=()
  for cmd in git docker; do
    if ! require_cmd "$cmd"; then missing+=("$cmd"); fi
  done

  if ! docker compose version >/dev/null 2>&1; then
    missing+=("docker compose plugin")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    warn "Missing: ${missing[*]}"
    if [[ "$NO_INSTALL_DEPS" == "1" ]]; then
      fail "Dependencies missing. Install them manually, or re-run without NO_INSTALL_DEPS=1"
    fi
    if ask_yn "Install missing dependencies with apt? [y/N] "; then
      install_deps
    else
      fail "Please install: ${missing[*]}"
    fi
  else
    ok "All dependencies present."
  fi
}

install_deps() {
  info "Installing dependencies (this requires root)..."
  if [[ $EUID -ne 0 ]]; then
    warn "Not running as root. Trying sudo..."
    SUDO=sudo
  else
    SUDO=""
  fi
  $SUDO apt-get update
  $SUDO apt-get install -y git curl
  if ! require_cmd docker; then
    $SUDO curl -fsSL https://get.docker.com | sh
  fi
  # Ensure compose plugin
  if ! docker compose version >/dev/null 2>&1; then
    $SUDO apt-get install -y docker-compose-plugin
  fi
  # Ensure current user can use docker
  if [[ "$EUID" -ne 0 ]]; then
    $SUDO usermod -aG docker "$USER" || true
    warn "Added $USER to docker group. If 'docker' still fails, log out & back in (or reboot)."
  fi
  ok "Dependencies installed."
}

clone_or_update() {
  info "Preparing project at $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Repo exists — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only origin main || git -C "$INSTALL_DIR" pull --ff-only
  else
    if [[ -d "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR")" ]]; then
      warn "$INSTALL_DIR is not empty. Cloning into $INSTALL_DIR/repo instead."
      INSTALL_DIR="$INSTALL_DIR/repo"
      mkdir -p "$INSTALL_DIR"
    fi
    info "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  cd "$INSTALL_DIR"
  ok "Project ready at $INSTALL_DIR"
}

setup_env() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    info "Created $INSTALL_DIR/.env from .env.example"
    warn "You MUST edit .env and add your YOUTUBE_API_KEY (TikTok/Instagram are optional)."
    info "After adding keys, either re-run this installer or:"
    info "  cd $INSTALL_DIR && docker compose up -d --build"
    if ask_yn "Do you want to edit .env now? [y/N] "; then
      if command -v nano >/dev/null 2>&1; then nano .env; else vi .env; fi
    fi
  else
    info ".env already exists — leaving it unchanged."
  fi
}

write_caddyfile() {
  info "Configuring Caddy domain..."
  local caddy="$INSTALL_DIR/deploy/Caddyfile"
  [[ -f "$caddy" ]] || return
  if ! grep -q "shorts.example.com" "$caddy"; then
    info "Caddyfile already has a custom domain."
    return
  fi

  local domain=""
  if [[ -n "${SHORTS_HUB_DOMAIN:-}" ]] && [[ "$SHORTS_HUB_DOMAIN" != "shortshub.example.com" ]]; then
    domain="$SHORTS_HUB_DOMAIN"
    info "Using domain from SHORTS_HUB_DOMAIN env var."
  else
    warn "Caddyfile still uses placeholder 'shorts.example.com'."
    domain="$(ask_value "Enter your domain (e.g. shorts.example.com), or press Enter to skip: ")"
  fi

  if [[ -n "$domain" ]]; then
    sed -i "s|shorts\.example\.com|$domain|g" "$caddy"
    DOMAIN="$domain"
    ok "Caddyfile set to $domain"
  else
    warn "Skipping — you'll need to edit $caddy later."
  fi
}

run_compose() {
  info "Building and starting containers (this can take a few minutes)..."
  # Use the docker group if available (non-root)
  local docker_cmd="docker"
  if ! groups | grep -q docker 2>/dev/null && [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then docker_cmd="sudo docker"; fi
  fi
  $docker_cmd compose up -d --build
  ok "Containers are up!"
}

print_next_steps() {
  cat <<EOF

${c_bold}${c_green}=== Shorts Hub installed successfully ===${c_reset}

${c_bold}Manage:${c_reset}
  cd $INSTALL_DIR
  docker compose ps                 # status
  docker compose logs -f backend    # watch backend/API logs
  docker compose logs -f caddy      # watch TLS/cert logs
  docker compose down               # stop
  docker compose pull && docker compose up -d  # update from this install

${c_bold}To expose over HTTPS via Caddy:${c_reset}
  1. Point DNS: an A record for your chosen subdomain -> your public IP
  2. On your router, forward ports 80 and 443 to this Proxmox host (IP of LXC/VM)
  3. Edit $INSTALL_DIR/deploy/Caddyfile and set your real domain
  4. Restart: cd $INSTALL_DIR && docker compose restart caddy
  Caddy auto-provisions + renews Let's Encrypt certs.

${c_bold}Recommended (security):${c_reset}
  This is a personal app exposed to the internet. Add at least basic_auth
  in the Caddyfile before going public. See the README.

${c_bold}Update the app later:${c_reset}
  cd $INSTALL_DIR && git pull && docker compose up -d --build
  (or re-run: curl -fsSL $INSTALL_URL | bash)
${c_reset}
EOF
}

# ---------------------------------------------------------------------------
main() {
  banner
  check_deps
  clone_or_update
  setup_env
  write_caddyfile
  run_compose
  print_next_steps
}

main "$@"
