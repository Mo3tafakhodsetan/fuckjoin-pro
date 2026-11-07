#!/usr/bin/env bash
set -Eeuo pipefail
REPO="Mo3tafakhodsetan/fuckjoin-pro"
BRANCH="main"
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
curl -fL --retry 3 "https://codeload.github.com/${REPO}/zip/refs/heads/${BRANCH}" -o "$TMP/update.zip"
python3 - "$TMP/update.zip" "$TMP/source" <<'PY'
import pathlib, sys, zipfile
archive, target = map(pathlib.Path, sys.argv[1:])
target.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for item in z.infolist():
        p = pathlib.PurePosixPath(item.filename)
        if p.is_absolute() or ".." in p.parts: raise SystemExit("Unsafe path in update archive")
        if len(p.parts) < 2: continue
        dest = target / pathlib.Path(*p.parts[1:])
        if item.is_dir(): dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(item))
PY
[[ -f "$TMP/source/docker-compose.yml" ]] || { echo "Update archive is incomplete" >&2; exit 1; }
mkdir -p "$DIR/backups"
cp -p "$DIR/.env" "$DIR/backups/.env.pre-update.$(date -u +%Y%m%dT%H%M%SZ)"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude='.env' --exclude='backups/' "$TMP/source/" "$DIR/"
else
  find "$DIR" -mindepth 1 -maxdepth 1 ! -name '.env' ! -name 'backups' -exec rm -rf {} +
  cp -a "$TMP/source/." "$DIR/"
fi
cd "$DIR"
docker compose config -q
docker compose up -d --build
echo "Update applied. Verify with: $DIR/fuckjoin status"
