# FuckJoin Pro

Standalone self-hosted foundation for Telegram automation management.

**Release status: v0.1.1 installer hardening.** This release includes a self-contained
Ubuntu installer, Docker Compose deployment, FastAPI health/API service, PostgreSQL and
Redis. The original project's complete Telegram/Telethon workflow, bot, worker and web
dashboard are not yet ported. No Telegram login or channel/media actions are performed yet.

## One-command install

Run on a fresh Ubuntu 22.04/24.04 server as root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Mo3tafakhodsetan/fuckjoin-pro/main/install.sh)
```

The installer downloads the repository archive itself, so it does not depend on sibling
files being present beside `install.sh`. It checks OS/architecture, warns about low RAM or
disk, installs Docker Engine/Compose if missing, prompts for Telegram credentials, generates
secrets, writes `.env` with mode 0600, starts services and waits for `/health`.

You can leave Telegram credentials blank during this foundation release. API ID and API Hash
must be entered together. Existing `.env` is preserved during reinstall/update.

## Services and security

- FastAPI: bound to `127.0.0.1` on port 8787 by default (`/health`, `/api/v1`, `/docs`)
- PostgreSQL 16 and Redis 7: persistent Docker volumes
- `.env`: mode 0600; contains generated application/database secrets

**Important:** The API currently has no authentication. Do not expose it publicly or proxy it
to the internet. Telegram credentials are collected for later integration only; this release
does not log in to Telegram.

## Management

```bash
sudo /opt/fuckjoin-pro/fuckjoin status
sudo /opt/fuckjoin-pro/fuckjoin restart
sudo /opt/fuckjoin-pro/fuckjoin update
sudo /opt/fuckjoin-pro/fuckjoin backup
sudo /opt/fuckjoin-pro/fuckjoin restore /path/to/database.sql
sudo /opt/fuckjoin-pro/fuckjoin logs
sudo /opt/fuckjoin-pro/fuckjoin uninstall
```

The updater downloads the current `main` branch archive and preserves `.env`, backups and
Docker volumes. It stores a copy of `.env` in `backups/` before replacing application files.
Database backup currently exports PostgreSQL only. Uninstall preserves volumes by default and
asks separately before deleting them.

## Next development milestones

1. Port and regression-test the upstream deep-link/media workflow.
2. Add isolated Telethon session lifecycle, safe cleanup and FloodWait-aware worker.
3. Add multi-user authorization, quotas, job queue and cancellation.
4. Add authenticated bilingual Persian/English dashboard and bot.
5. Add TLS, scheduled backups, restore validation and release-based updater.

Review the upstream repository's license and preserve required notices before redistributing
any upstream source. This initial scaffold is independently authored.
