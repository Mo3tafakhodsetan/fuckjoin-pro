from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from contextlib import suppress

from aiogram import Bot
from redis.asyncio import Redis
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerChannel

from app.jobs.queue import JOB_PREFIX, QUEUE_KEY, JobQueue
from app.telegram.session import TelegramSessionManager

logger = logging.getLogger(__name__)
LINK_RE = re.compile(r"^https?://t\.me/(?:c/\d+|[A-Za-z][A-Za-z0-9_]{3,})/\d+(?:\?[^\s]*)?/?$")


def parse_message_link(url: str) -> tuple[str, int, bool]:
    """Accept only direct t.me message links; never follows bot/deep-link redirects."""
    value = url.strip()
    if not LINK_RE.fullmatch(value):
        raise ValueError("Only direct t.me/channel-or-group/message links are supported")
    parts = value.split("?", 1)[0].rstrip("/").split("/")
    if len(parts) >= 6 and parts[-3] == "c":
        return parts[-2], int(parts[-1]), True
    return parts[-2], int(parts[-1]), False


class DownloadWorker:
    def __init__(self, redis_url: str, jobs: JobQueue, sessions: TelegramSessionManager,
                 bot_token: str, download_dir: str = "/data/downloads"):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.jobs = jobs
        self.sessions = sessions
        self.bot = Bot(bot_token) if bot_token else None
        self.download_dir = Path(download_dir)
        self.task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not self.bot:
            logger.info("Download worker disabled: TELEGRAM_BOT_TOKEN is not configured")
            return
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.task = asyncio.create_task(self._run(), name="telegram-download-worker")

    async def close(self) -> None:
        self._stopping.set()
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.redis.aclose()
        if self.bot:
            await self.bot.session.close()

    async def _run(self) -> None:
        while not self._stopping.is_set():
            item = await self.redis.blpop(QUEUE_KEY, timeout=2)
            if not item:
                continue
            try:
                job = json.loads(item[1])
                await self._process(job)
            except Exception:
                logger.exception("Unexpected worker error")

    async def _process(self, job: dict) -> None:
        job_id = job["id"]
        chat_id = int(job["chat_id"])
        try:
            current = await self.jobs.get(job_id)
            if current and current.get("cancel_requested") == "1":
                await self.jobs.update(job_id, status="cancelled")
                return
            await self.jobs.update(job_id, status="processing")
            if not await self.sessions.status() or not (await self.sessions.status()).get("authorized"):
                raise RuntimeError("A logged-in Telegram user session is required")
            client = self.sessions.client
            if client is None:
                raise RuntimeError("Telegram session is unavailable")
            key, message_id, is_private = parse_message_link(job["url"])
            entity = await client.get_entity(PeerChannel(int(key))) if is_private else await client.get_entity(key)
            message = await client.get_messages(entity, ids=message_id)
            if not message:
                raise RuntimeError("Message was not found or is not accessible to this account")
            if getattr(message, "noforwards", False):
                raise RuntimeError("This message is protected against forwarding/downloading")
            if not message.media:
                raise RuntimeError("The linked message does not contain downloadable media")
            filename = await client.download_media(message, file=str(self.download_dir / f"{job_id}_"))
            if not filename:
                raise RuntimeError("Telegram did not return a downloaded file")
            path = Path(filename)
            try:
                current = await self.jobs.get(job_id)
                if current and current.get("cancel_requested") == "1":
                    await self.jobs.update(job_id, status="cancelled")
                    return
                with path.open("rb") as media_file:
                    await self.bot.send_document(chat_id, document=media_file, caption=f"دانلود با موفقیت انجام شد\nشناسه: {job_id}")
                await self.jobs.update(job_id, status="completed", file_name=path.name)
            finally:
                path.unlink(missing_ok=True)
        except FloodWaitError as exc:
            await self.jobs.update(job_id, status="queued", error=f"FloodWait: retry after {exc.seconds}s")
            await asyncio.sleep(min(exc.seconds, 3600))
            data = await self.jobs.get(job_id)
            if data and data.get("status") == "queued":
                await self.redis.rpush(QUEUE_KEY, json.dumps(job, separators=(",", ":")))
        except Exception as exc:
            logger.exception("Download job %s failed", job_id)
            await self.jobs.update(job_id, status="failed", error=str(exc)[:500])
            if self.bot:
                with suppress(Exception):
                    await self.bot.send_message(chat_id, f"❌ پردازش ناموفق بود: {str(exc)[:300]}\nشناسه: {job_id}")
