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
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetBotCallbackAnswerRequest

from app.jobs.queue import JOB_PREFIX, QUEUE_KEY, JobQueue
from app.telegram.session import TelegramSessionManager

logger = logging.getLogger(__name__)

LINK_RE = re.compile(r"^https?://t\.me/(?:\+[\w-]+|joinchat/[\w-]+|c/\d+|[A-Za-z][A-Za-z0-9_]{3,})/?(?:\d+)?(?:\?[^\s]*)?$")


def parse_message_link(url: str) -> tuple[str | None, int, bool]:
    """Parse direct message links, invite links, or channel/bot usernames."""
    value = url.strip()
    if not LINK_RE.fullmatch(value):
        raise ValueError("Only valid t.me links are supported")
    
    if "+" in value or "/joinchat/" in value:
        return value, 0, False

    parts = value.split("?", 1)[0].rstrip("/").split("/")
    if len(parts) >= 6 and parts[-3] == "c":
        return parts[-2], int(parts[-1]), True
    if len(parts) >= 4 and parts[-1].isdigit():
        return parts[-2], int(parts[-1]), False
    return parts[-1], 0, False


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
        joined_entities = []

        try:
            current = await self.jobs.get(job_id)
            if current and current.get("cancel_requested") == "1":
                await self.jobs.update(job_id, status="cancelled")
                return

            await self.jobs.update(job_id, status="processing")
            status_info = await self.sessions.status()
            if not status_info or not status_info.get("authorized"):
                raise RuntimeError("A logged-in Telegram user session is required")

            client = self.sessions.client
            if client is None:
                raise RuntimeError("Telegram session is unavailable")

            url = job["url"]
            key, message_id, is_private = parse_message_link(url)

            # 1. Handle Join Chains & Private Invites
            if key and ("+" in url or "/joinchat/" in url):
                hash_part = url.split("+")[-1].split("?")[0].split("/joinchat/")[-1]
                with suppress(Exception):
                    updates = await client(ImportChatInviteRequest(hash_part))
                    for chat in getattr(updates, "chats", []):
                        joined_entities.append(chat)

            entity = None
            if is_private and isinstance(key, str) and key.isdigit():
                entity = await client.get_entity(PeerChannel(int(key)))
            elif key and not is_private and ("+" not in url and "/joinchat/" not in url):
                try:
                    entity = await client.get_entity(key)
                    if message_id == 0:
                        await client(JoinChannelRequest(entity))
                        joined_entities.append(entity)
                except Exception:
                    pass

            # 2. Retrieve Media Message
            message = None
            if entity and message_id > 0:
                message = await client.get_messages(entity, ids=message_id)
            else:
                target = entity or (key if key else url)
                async for msg in client.iter_messages(target, limit=10):
                    if msg.media:
                        message = msg
                        break
                    # Intermediary bot inline button handling
                    if msg.reply_markup and getattr(msg.reply_markup, 'rows', None):
                        for row in msg.reply_markup.rows:
                            for button in row.buttons:
                                if getattr(button, 'url', None) and ('t.me/' in button.url):
                                    with suppress(Exception):
                                        sub_key, _, _ = parse_message_link(button.url)
                                        if sub_key:
                                            sub_ent = await client.get_entity(sub_key)
                                            await client(JoinChannelRequest(sub_ent))
                                            joined_entities.append(sub_ent)
                                if getattr(button, 'data', None):
                                    with suppress(Exception):
                                        await client(GetBotCallbackAnswerRequest(
                                            peer=target,
                                            msg_id=msg.id,
                                            data=button.data
                                        ))

            if not message or not message.media:
                raise RuntimeError("Target media message was not found through the chain")

            if getattr(message, "noforwards", False):
                raise RuntimeError("This message is protected against forwarding/downloading")

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
                    await self.bot.send_document(
                        chat_id,
                        document=media_file,
                        caption=f"✅ دانلود و پردازش با موفقیت انجام شد
شناسه جاب: {job_id}"
                    )
                await self.jobs.update(job_id, status="completed", file_name=path.name)
            finally:
                path.unlink(missing_ok=True)

        except FloodWaitError as exc:
            logger.warning("FloodWait encountered: waiting for %s seconds", exc.seconds)
            await self.jobs.update(job_id, status="queued", error=f"FloodWait: retry after {exc.seconds}s")
            if self.bot:
                with suppress(Exception):
                    await self.bot.send_message(chat_id, f"⏳ محدودیت FloodWait تلگرام: تلاش مجدد پس از {exc.seconds} ثانیه")
            await asyncio.sleep(min(exc.seconds, 3600))
            data = await self.jobs.get(job_id)
            if data and data.get("status") == "queued":
                await self.redis.rpush(QUEUE_KEY, json.dumps(job, separators=(",", ":")))
        except Exception as exc:
            logger.exception("Download job %s failed", job_id)
            await self.jobs.update(job_id, status="failed", error=str(exc)[:500])
            if self.bot:
                with suppress(Exception):
                    await self.bot.send_message(chat_id, f"❌ پردازش ناموفق بود: {str(exc)[:300]}
شناسه: {job_id}")

        finally:
            # Auto-leave temporary channels/groups after downloading or error
            if self.sessions and self.sessions.client:
                client = self.sessions.client
                for ent in joined_entities:
                    with suppress(Exception):
                        await client(LeaveChannelRequest(ent))
                        logger.info("Successfully left temporary entity: %s", ent)
