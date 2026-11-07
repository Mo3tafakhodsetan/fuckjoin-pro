# FuckJoin Pro

Self-hosted Telegram automation foundation. **Release: v0.5.0 — admin quotas and request history.**

This release retains the v0.2.0 FastAPI + Telethon session engine and adds an allow-listed Telegram Bot API control bot. The admin bot supports `/start`, `/help`, `/admin`, and `/status`. It does not expose login codes, 2FA passwords, session strings, or arbitrary account actions.

This release adds a Redis-backed worker for direct media message links in chats the logged-in account can already access. It does not automatically join groups/channels, follow bot handoffs, bypass membership gates, or extract protected content.

## Install

On a fresh Ubuntu 22.04/24.04 server as root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Mo3tafakhodsetan/fuckjoin-pro/main/install.sh)
```

The installer deploys Docker Compose, asks for a Telegram Bot Token, Telegram API ID/API Hash, and numeric admin Telegram ID(s). The admin bot starts only when both a valid bot token and at least one admin ID are configured. Telegram API ID and API Hash must be supplied together. Existing `.env` is preserved on reinstall/update.

## Services and security

- FastAPI is bound to `127.0.0.1:8787` by default.
- PostgreSQL 16 and Redis 7 use persistent Docker volumes.
- `.env` is written with mode `0600`.
- Telegram session data is stored in a dedicated Docker volume with owner-only file permissions.
- Session API endpoints require `X-App-Secret` and should remain localhost-only.
- The admin bot uses a numeric Telegram user-ID allowlist. Unauthorized users receive no administrative data.
- Never share the bot token, `APP_SECRET`, Telegram login code, 2FA password, or session file.

## Admin bot commands

- `/start` or `/help` — help
- `/admin` — administrative command summary
- `/status` — Telethon session configuration, connection, and authorization status

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_IDS` in `.env`, then run:

```bash
sudo /opt/fuckjoin-pro/fuckjoin restart
sudo /opt/fuckjoin-pro/fuckjoin logs
```

`TELEGRAM_ADMIN_IDS` accepts comma-separated numeric Telegram user IDs. Do not use usernames as an access-control identifier.

## Protected local session API

All endpoints require `X-App-Secret: <APP_SECRET>`:

- `GET /api/v1/telegram/session`
- `POST /api/v1/telegram/login/send-code` with `{"phone":"+..."}`
- `POST /api/v1/telegram/login/verify` with `{"code":"12345"}`
- If Telegram requests 2-step verification, repeat `/login/verify` with `{"code":"12345","password":"..."}`
- `POST /api/v1/telegram/logout`

Example (run on the server; do not paste secrets into shared chats):

```bash
APP_SECRET="$(grep '^APP_SECRET=' .env | cut -d= -f2- | tr -d '\"')"
curl -sS -H "X-App-Secret: $APP_SECRET" http://127.0.0.1:8787/api/v1/telegram/session
```

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

## Development roadmap

1. Port and regression-test the original project's deep-link resolver and media workflow.
2. Add Redis-backed job queue, worker lifecycle, cancellation, and FloodWait-aware retry handling.
3. Add per-user authorization, quotas, audit events, and safe concurrency limits.
4. Add a bilingual Persian/English dashboard.
5. Add TLS guidance, scheduled backup validation, and signed/release-based updates.

Review the upstream repository's license and preserve required notices before redistributing upstream source. This scaffold does not claim feature parity with the upstream project.


## Download jobs (v0.4.0)

Create a job using the local API (only allow-listed admin IDs may be target chats):

```bash
curl -sS -X POST http://127.0.0.1:8787/api/v1/jobs \
  -H "X-App-Secret: $APP_SECRET" -H 'Content-Type: application/json' \
  -d '{"message_url":"https://t.me/example/123","chat_id":123456789}'
```

- `GET /api/v1/jobs/{job_id}` checks status.
- `DELETE /api/v1/jobs/{job_id}` requests cancellation.
- The account must already have access to the source chat.
- Only direct `t.me/<username>/<message_id>` or `t.me/c/<channel_id>/<message_id>` links are accepted.
- Media is delivered to the allow-listed admin's private chat and the temporary local file is deleted.
- Telegram protected-content messages are refused.
- FloodWait is respected; retry is delayed instead of repeatedly hitting Telegram.

Set the `APP_SECRET` shell variable as shown in the protected API section above before using the example.


### Version 0.5.0 — admin usage controls

- Send a supported direct `https://t.me/<username>/<message_id>` or `https://t.me/c/<channel_id>/<message_id>` link to the admin bot.
- `/quota` shows today's UTC request count and configured daily limit.
- `/history` lists the latest 10 requests for the calling admin.
- Set `DAILY_JOB_LIMIT` in `.env` (default: `20`).
- Job metadata and user history are retained in Redis for up to 30 days.

Only allow-listed admin IDs can submit jobs. The logged-in Telegram account must already have legitimate access to the chat. Protected content is not bypassed.
