#!/usr/bin/env bash
set -Eeuo pipefail
REPO="Mo3tafakhodsetan/fuckjoin-pro"
BRANCH="main"
PROJECT_DIR="${FUCKJOIN_DIR:-/opt/fuckjoin-pro}"
TMP_DIR=""
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn(){ printf '\n\033[1;33mWARNING: %s\033[0m\n' "$*" >&2; }
die(){ printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
cleanup(){ [[ -z "$TMP_DIR" ]] || rm -rf "$TMP_DIR"; }
trap cleanup EXIT
on_error(){ local rc=$?; echo "Installer failed at line ${BASH_LINENO[0]} (exit ${rc})." >&2; exit "$rc"; }
trap on_error ERR

[[ $EUID -eq 0 ]] || die "Run as root: sudo bash install.sh"
[[ -r /etc/os-release ]] || die "Cannot identify Linux distribution."
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "Ubuntu 22.04/24.04 is currently supported (detected: ${PRETTY_NAME:-unknown})."
[[ "$(uname -m)" =~ ^(x86_64|aarch64|arm64)$ ]] || die "Unsupported architecture: $(uname -m)"
command -v curl >/dev/null 2>&1 || { apt-get update; apt-get install -y curl ca-certificates; }
command -v python3 >/dev/null 2>&1 || { apt-get update; apt-get install -y python3; }
command -v openssl >/dev/null 2>&1 || { apt-get update; apt-get install -y openssl; }

say "FuckJoin Pro interactive installer"
echo "Target directory: $PROJECT_DIR"
read -r -p "Continue installation? [y/N]: " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

mem_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
disk_kb="$(df -Pk "$(dirname "$PROJECT_DIR")" 2>/dev/null | awk 'NR==2 {print $4}')"
disk_mb="$(( ${disk_kb:-0} / 1024 ))"
(( mem_mb >= 1800 )) || warn "Detected ${mem_mb} MB RAM. 2 GB or more is recommended."
(( disk_mb >= 5000 )) || warn "Less than 5 GB free disk space detected."

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  say "Installing Docker Engine and Compose plugin"
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  [[ -s /etc/apt/keyrings/docker.asc ]] || curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch="$(dpkg --print-architecture)"
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$arch" "$codename" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin installation failed."
systemctl enable --now docker

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || true)"
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/docker-compose.yml" && -f "$SCRIPT_DIR/app/main.py" ]]; then
  SOURCE_DIR="$SCRIPT_DIR"
else
  say "Downloading project source from GitHub"
  TMP_DIR="$(mktemp -d)"
  curl -fL --retry 3 "https://codeload.github.com/${REPO}/zip/refs/heads/${BRANCH}" -o "$TMP_DIR/source.zip"
  python3 - "$TMP_DIR/source.zip" "$TMP_DIR/source" <<'PY'
import pathlib, sys, zipfile
archive, target = map(pathlib.Path, sys.argv[1:])
target.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for item in z.infolist():
        p = pathlib.PurePosixPath(item.filename)
        if p.is_absolute() or ".." in p.parts:
            raise SystemExit("Unsafe path in source archive")
        if len(p.parts) < 2: continue
        dest = target / pathlib.Path(*p.parts[1:])
        if item.is_dir(): dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(item))
PY
  SOURCE_DIR="$TMP_DIR/source"
fi
[[ -f "$SOURCE_DIR/docker-compose.yml" && -f "$SOURCE_DIR/Dockerfile" ]] || die "Source is incomplete. Check the GitHub main branch."
if [[ -e "$PROJECT_DIR" && -f "$PROJECT_DIR/.env" ]]; then
  read -r -p "Existing installation found. Preserve its .env and data? [Y/n]: " preserve
  [[ "$preserve" =~ ^[Nn]$ ]] && die "Refusing to overwrite an existing installation."
fi
mkdir -p "$PROJECT_DIR"
SOURCE_REAL="$(realpath "$SOURCE_DIR")"
PROJECT_REAL="$(realpath -m "$PROJECT_DIR")"
if [[ "$SOURCE_REAL" != "$PROJECT_REAL" ]]; then
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude='.env' --exclude='backups/' "$SOURCE_DIR/" "$PROJECT_DIR/"
  else
    find "$PROJECT_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' ! -name 'backups' -exec rm -rf {} +
    cp -a "$SOURCE_DIR/." "$PROJECT_DIR/"
  fi
fi
cd "$PROJECT_DIR"
chmod 700 "$PROJECT_DIR"
chmod +x install.sh fuckjoin scripts/update.sh 2>/dev/null || true

if [[ -f .env ]]; then
  say "Existing configuration detected; keeping it unchanged"
else
  say "Telegram setup (credentials can be left blank; Telegram engine is not integrated yet)"
  read -r -s -p "Telegram Bot Token (optional): " BOT_TOKEN; echo
  read -r -p "Telegram API ID (optional): " API_ID
  read -r -s -p "Telegram API Hash (optional): " API_HASH; echo
  read -r -p "Admin Telegram ID(s), comma-separated (optional): " ADMIN_IDS
  [[ -z "$API_ID" || "$API_ID" =~ ^[0-9]+$ ]] || die "API ID must contain digits only."
  if [[ -n "$API_ID" && -z "$API_HASH" ]] || [[ -z "$API_ID" && -n "$API_HASH" ]]; then die "API ID and API Hash must be supplied together."; fi
  [[ -z "$ADMIN_IDS" || "$ADMIN_IDS" =~ ^[0-9]+(,[0-9]+)*$ ]] || die "Admin IDs must be comma-separated numeric Telegram IDs."
  APP_SECRET="$(openssl rand -hex 32)"
  DB_PASSWORD="$(openssl rand -hex 24)"
  APP_PORT="${APP_PORT:-8787}"
  [[ "$APP_PORT" =~ ^[0-9]+$ ]] && (( APP_PORT >= 1024 && APP_PORT <= 65535 )) || die "APP_PORT must be between 1024 and 65535."
  export APP_SECRET DB_PASSWORD BOT_TOKEN API_ID API_HASH ADMIN_IDS APP_PORT
  python3 - <<'PY'
import os
from pathlib import Path
def q(v): return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
v = {
 "APP_NAME":"FuckJoin Pro", "APP_ENV":"production", "APP_PORT":os.environ["APP_PORT"], "LOG_LEVEL":"INFO",
 "DATABASE_URL":f"postgresql+psycopg://fuckjoin:{os.environ['DB_PASSWORD']}@db:5432/fuckjoin",
 "REDIS_URL":"redis://redis:6379/0", "APP_SECRET":os.environ["APP_SECRET"], "DB_PASSWORD":os.environ["DB_PASSWORD"],
 "TELEGRAM_BOT_TOKEN":os.environ["BOT_TOKEN"], "TELEGRAM_API_ID":os.environ["API_ID"],
 "TELEGRAM_API_HASH":os.environ["API_HASH"], "TELEGRAM_ADMIN_IDS":os.environ["ADMIN_IDS"]}
Path(".env").write_text("".join(f"{k}={q(val)}\n" for k,val in v.items()), encoding="utf-8")
Path(".env").chmod(0o600)
PY
  unset APP_SECRET DB_PASSWORD BOT_TOKEN API_ID API_HASH ADMIN_IDS
fi

say "Validating Compose configuration"
docker compose config -q
say "Building and starting services"
docker compose up -d --build
PORT="$(sed -n 's/^APP_PORT="\{0,1\}\([0-9]*\)"\{0,1\}$/\1/p' .env | head -n1)"
PORT="${PORT:-8787}"
say "Waiting for API health check"
healthy=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then healthy=1; break; fi
  sleep 2
done
if (( healthy )); then
  say "Installation completed"
  echo "API: http://127.0.0.1:${PORT}"
  echo "Health: /health"
  echo "Management: $PROJECT_DIR/fuckjoin"
  echo "Security: API has no authentication yet; keep it bound to localhost."
else
  docker compose logs --tail=80 || true
  die "Health check failed. Run: cd '$PROJECT_DIR' && ./fuckjoin logs"
fi
