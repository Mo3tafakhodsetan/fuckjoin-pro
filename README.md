# FuckJoin Pro

Standalone self-hosted foundation for Telegram automation management.

**Release status: v0.1.0 foundation.** This ZIP contains an interactive Ubuntu installer,
Docker Compose deployment, FastAPI health/API service, PostgreSQL and Redis. The original
project's complete Telegram/Telethon workflow, bot, worker and web dashboard are not yet
ported. The engine integration is a subsequent development step; this package does not
claim those features are already operational.

## Install

After uploading this repository to your GitHub account:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/fuckjoin-pro/main/install.sh)
```

The command above is a template: replace `YOUR_GITHUB_USERNAME` after creating the repository.

Or extract the ZIP and run `sudo bash install.sh`.

The installer supports Ubuntu 22.04/24.04, checks architecture, installs Docker if needed,
asks for Telegram Bot Token/API ID/API Hash/admin ID, generates secrets, writes `.env`
with mode 0600, starts the containers and checks health.

## Services

- FastAPI: localhost port 8787 (`/health`, `/api/v1`, `/docs`)
- PostgreSQL 16 (persistent Docker volume)
- Redis 7 (persistent Docker volume)

Telegram credentials are stored for later engine integration. This release does not perform
Telegram login or channel/media actions yet. The API is not authenticated; do not expose it
publicly. Keep it on localhost or behind a secured reverse proxy.

## Management

Run from `/opt/fuckjoin-pro`:

```bash
./fuckjoin status
./fuckjoin restart
./fuckjoin update
./fuckjoin backup
./fuckjoin restore /path/to/database.sql
./fuckjoin logs
./fuckjoin uninstall
```

Uninstall preserves data by default and asks separately before deleting Docker volumes.

## Next development milestones

1. Port and regression-test the upstream deep-link/media workflow.
2. Add isolated Telethon session lifecycle, safe cleanup and FloodWait-aware worker.
3. Add multi-user authorization, quotas, job queue and cancellation.
4. Add authenticated bilingual Persian/English dashboard and bot.
5. Add TLS, scheduled backups, restore validation and robust release updater.

Review the upstream repository's license and preserve required notices before redistributing
any upstream source. This initial scaffold is independently authored.
