#!/usr/bin/env bash
set -Eeuo pipefail
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
