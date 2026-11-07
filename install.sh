#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_DIR="${FUCKJOIN_DIR:-/opt/fuckjoin-pro}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/scripts/installer-lib.sh"
[[ $EUID -eq 0 ]] || die "Run as root: sudo bash install.sh"
[[ -f /etc/os-release ]] || die "Cannot identify Linux distribution."
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "Ubuntu 22.04/24.04 is currently supported."
[[ "$(uname -m)" =~ ^(x86_64|aarch64|arm64)$ ]] || die "Unsupported architecture."
say "FuckJoin Pro interactive installer"
read -r -p "Install to $PROJECT_DIR? [y/N]: " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin unavailable."
systemctl enable --now docker

if [[ "$SCRIPT_DIR" != "$PROJECT_DIR" ]]; then
  mkdir -p "$PROJECT_DIR"
  cp -a "$SCRIPT_DIR/." "$PROJECT_DIR/"
fi
cd "$PROJECT_DIR"

say "Telegram credentials (can be left blank for now)"
read -r -s -p "Bot Token: " BOT_TOKEN; echo
read -r -p "API ID: " API_ID
read -r -s -p "API Hash: " API_HASH; echo
read -r -p "Admin Telegram ID(s), comma-separated: " ADMIN_IDS

APP_SECRET="$(openssl rand -hex 32)"
DB_PASSWORD="$(openssl rand -hex 24)"
cat > .env <<EOF
APP_NAME=FuckJoin Pro
APP_ENV=production
APP_PORT=8787
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://fuckjoin:${DB_PASSWORD}@db:5432/fuckjoin
REDIS_URL=redis://redis:6379/0
APP_SECRET=${APP_SECRET}
DB_PASSWORD=${DB_PASSWORD}
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
TELEGRAM_API_ID=${API_ID}
TELEGRAM_API_HASH=${API_HASH}
TELEGRAM_ADMIN_IDS=${ADMIN_IDS}
EOF
chmod 600 .env
unset BOT_TOKEN API_HASH APP_SECRET DB_PASSWORD

say "Building and starting containers"
docker compose up -d --build
sleep 5
if curl -fsS http://127.0.0.1:8787/health; then
  echo
  say "Installation completed"
  echo "API: http://127.0.0.1:8787"
  echo "Docs: http://127.0.0.1:8787/docs"
  echo "Management: $PROJECT_DIR/fuckjoin"
else
  docker compose logs --tail=80
  die "Health check failed. Run: cd '$PROJECT_DIR' && docker compose logs"
fi
