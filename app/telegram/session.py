from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession


class TelegramSessionManager:
    """Owns exactly one Telethon client and persists its StringSession securely."""

    def __init__(self, api_id: str, api_hash: str, session_path: str = "/data/telegram.session"):
        self.api_id = int(api_id) if api_id else None
        self.api_hash = api_hash
        self.session_path = Path(session_path)
        self.client: TelegramClient | None = None
        self._lock = asyncio.Lock()
        self._phone: str | None = None
        self._phone_code_hash: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_id and self.api_hash)

    def _new_client(self) -> TelegramClient:
        session = self.session_path.read_text(encoding="utf-8").strip() if self.session_path.exists() else ""
        return TelegramClient(StringSession(session), self.api_id, self.api_hash)

    async def start(self) -> None:
        if not self.configured:
            return
        async with self._lock:
            if self.client is None:
                self.client = self._new_client()
            if not self.client.is_connected():
                await self.client.connect()

    async def close(self) -> None:
        async with self._lock:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            self.client = None

    async def status(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "connected": False, "authorized": False}
        await self.start()
        assert self.client is not None
        authorized = await self.client.is_user_authorized()
        return {"configured": True, "connected": self.client.is_connected(), "authorized": authorized}

    async def send_code(self, phone: str) -> dict[str, str]:
        if not self.configured:
            raise ValueError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH first")
        if not phone or len(phone) > 32:
            raise ValueError("Invalid phone number")
        await self.start()
        assert self.client is not None
        async with self._lock:
            sent = await self.client.send_code_request(phone)
            self._phone = phone
            self._phone_code_hash = sent.phone_code_hash
        return {"status": "code_sent"}

    def _persist(self) -> None:
        assert self.client is not None
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.session_path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(self.client.session.save())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, self.session_path)
        os.chmod(self.session_path, 0o600)

    async def sign_in(self, code: str, password: str | None = None) -> dict[str, str]:
        if not self.configured:
            raise ValueError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH first")
        if not self._phone or not self._phone_code_hash:
            raise ValueError("Request a login code first")
        await self.start()
        assert self.client is not None
        async with self._lock:
            try:
                await self.client.sign_in(phone=self._phone, code=code, phone_code_hash=self._phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    return {"status": "password_required"}
                await self.client.sign_in(password=password)
            self._persist()
            self._phone = None
            self._phone_code_hash = None
        return {"status": "authorized"}

    async def logout(self) -> dict[str, str]:
        if not self.configured:
            raise ValueError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH first")
        await self.start()
        assert self.client is not None
        async with self._lock:
            await self.client.log_out()
            self.session_path.unlink(missing_ok=True)
            self._phone = None
            self._phone_code_hash = None
        return {"status": "logged_out"}
