# Changelog

## 0.4.0
- Added Redis-backed download job queue and status/cancel API.
- Added worker for downloading media from direct Telegram message links that the logged-in account can already access.
- Added FloodWait-aware retry and protected-message refusal.
- No automatic group/channel joining, bot handoff traversal, membership-gate bypass, or protected-content extraction.

## 0.3.0
- Added allow-listed Telegram admin bot.
- Added `/start`, `/help`, `/admin`, and `/status`.

## 0.2.0
- Added Telethon session management and protected local API.

## 0.5.0
- Added admin-bot link submission, per-admin daily quotas, and request history.
- Added Redis-backed atomic quota reservation and 30-day job metadata retention.
- Fixed parsing of private Telegram message links (`t.me/c/<channel>/<message>`).
- Added `/quota` and `/history` admin commands.
