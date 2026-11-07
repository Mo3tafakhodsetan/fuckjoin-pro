from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from app.jobs.queue import DailyLimitExceeded, JobQueue
from app.jobs.worker import parse_message_link

from app.telegram.session import TelegramSessionManager

logger = logging.getLogger(__name__)


class AdminBot:
    """Small, allow-listed Telegram control bot; never exposes session secrets."""

    def __init__(self, token: str, admin_ids: str, sessions: TelegramSessionManager, jobs: JobQueue | None = None):
        self.token = token.strip()
        self.admin_ids = {int(value.strip()) for value in admin_ids.split(",") if value.strip().isdigit()}
        self.sessions = sessions
        self.jobs = jobs
        self.bot: Bot | None = None
        self.dispatcher: Dispatcher | None = None
        self.task: asyncio.Task | None = None

    @property
    def configured(self) -> bool:
        return bool(self.token and self.admin_ids)

    def _allowed(self, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in self.admin_ids)

    async def start(self) -> None:
        if not self.configured:
            logger.info("Admin bot disabled: token or numeric admin IDs are missing")
            return
        self.bot = Bot(token=self.token)
        # Validate the token before declaring startup successful.
        await self.bot.get_me()
        self.dispatcher = Dispatcher()

        @self.dispatcher.message(Command("start", "help"))
        async def help_handler(message: Message) -> None:
            if not self._allowed(message):
                await message.answer("⛔ دسترسی مجاز نیست.")
                return
            await message.answer(
                "🤖 FuckJoin Pro Admin Bot\n\n"
                "/status — وضعیت اتصال حساب تلگرام\n"
                "/admin — راهنمای مدیریت\n"
                "/quota — سهمیه روزانه\n"
                "/history — تاریخچه درخواست‌ها\n\n"
                "این ربات فقط برای مدیران مجاز است؛ کد ورود و رمز دومرحله‌ای را در چت ارسال نکنید."
            )

        @self.dispatcher.message(Command("admin"))
        async def admin_handler(message: Message) -> None:
            if not self._allowed(message):
                await message.answer("⛔ دسترسی مجاز نیست.")
                return
            await message.answer(
                "پنل مدیریتی نسخه 0.5.0\n"
                "• /status : وضعیت نشست\n"
                "• /quota : سهمیه روزانه\n"
                "• /history : ده درخواست اخیر\n"
                "• ارسال لینک مستقیم پیام تلگرام برای شروع پردازش\n"
                "فقط رسانه‌ای پردازش می‌شود که حساب به آن دسترسی مجاز داشته باشد."
            )

        @self.dispatcher.message(Command("status"))
        async def status_handler(message: Message) -> None:
            if not self._allowed(message):
                await message.answer("⛔ دسترسی مجاز نیست.")
                return
            try:
                status = await self.sessions.status()
                configured = "فعال" if status["configured"] else "تنظیم نشده"
                connected = "متصل" if status["connected"] else "قطع"
                authorized = "مجاز" if status["authorized"] else "وارد نشده"
                await message.answer(
                    "📊 وضعیت حساب تلگرام\n"
                    f"API: {configured}\nاتصال: {connected}\nاحراز هویت: {authorized}"
                )
            except Exception:
                logger.exception("Unable to retrieve Telegram session status")
                await message.answer("⚠️ دریافت وضعیت ناموفق بود. گزارش سرویس را بررسی کنید.")

        @self.dispatcher.message(Command("quota"))
        async def quota_handler(message: Message) -> None:
            if not self._allowed(message):
                await message.answer("⛔ دسترسی مجاز نیست.")
                return
            used = await self.jobs.quota_used(message.from_user.id)
            await message.answer(f"📊 سهمیه امروز: {used}/{self.jobs.daily_limit} درخواست")

        @self.dispatcher.message(Command("history"))
        async def history_handler(message: Message) -> None:
            if not self._allowed(message):
                await message.answer("⛔ دسترسی مجاز نیست.")
                return
            rows = await self.jobs.history(message.from_user.id, 10)
            if not rows:
                await message.answer("هنوز درخواستی ثبت نشده است.")
                return
            lines = ["🗂 ده درخواست اخیر:"]
            for row in rows:
                lines.append(f"• {row.get('id', '')[:8]} — {row.get('status', 'unknown')} — {row.get('created_at', '')[:16]}")
            await message.answer("\n".join(lines))

        @self.dispatcher.message()
        async def submit_link_handler(message: Message) -> None:
            if not self._allowed(message) or not message.text:
                return
            text = message.text.strip()
            if not text.startswith(("https://t.me/", "http://t.me/")):
                return
            try:
                parse_message_link(text)
                job = await self.jobs.enqueue(text, message.from_user.id)
                await message.answer(f"✅ درخواست ثبت شد.\nشناسه: {job['id']}\nبرای پیگیری از /history استفاده کنید.")
            except ValueError as exc:
                await message.answer(f"لینک پشتیبانی نمی‌شود: {exc}")
            except DailyLimitExceeded as exc:
                await message.answer(f"سهمیه روزانه شما تکمیل شده است (حداکثر {exc.args[0]} درخواست).")
            except Exception:
                logger.exception("Unable to enqueue Telegram link")
                await message.answer("ثبت درخواست ناموفق بود؛ گزارش سرویس را بررسی کنید.")

        self.task = asyncio.create_task(self.dispatcher.start_polling(self.bot), name="telegram-admin-bot")
        await asyncio.sleep(0)
        if self.task.done():
            await self.task
        logger.info("Telegram admin bot polling started")

    async def close(self) -> None:
        if self.dispatcher:
            with suppress(Exception):
                await self.dispatcher.stop_polling()
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        if self.bot:
            await self.bot.session.close()
            self.bot = None
