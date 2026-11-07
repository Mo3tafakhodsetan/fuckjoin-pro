# Changelog

## 0.6.0
- Added Telegram join-chain traversal and invite-link handling (`t.me/+...`, `joinchat`).
- Added automatic temporary membership management and post-download auto-leave functionality.
- Added support for intermediary sponsor bot inline buttons and verification callbacks.
- Enhanced FloodWait reporting and retry management.

## 0.5.0
- Added admin-bot link submission, per-admin daily quotas, and request history.
- Added Redis-backed atomic quota reservation and 30-day job metadata retention.
- Fixed parsing of private Telegram message links (`t.me/c/<channel>/<message>`).
- Added `/quota` and `/history` admin commands.
