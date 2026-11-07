from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

QUEUE_KEY = "fuckjoin:jobs:pending"
JOB_PREFIX = "fuckjoin:job:"


class DailyLimitExceeded(Exception):
    pass


class JobQueue:
    def __init__(self, redis_url: str, daily_limit: int = 20):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.daily_limit = max(1, daily_limit)

    async def close(self) -> None:
        await self.redis.aclose()

    async def enqueue(self, message_url: str, chat_id: int) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        day_key = f"fuckjoin:quota:{chat_id}:{now:%Y%m%d}"
        # Atomic quota reservation: concurrent requests cannot exceed the limit.
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(day_key)
            pipe.expire(day_key, 60 * 60 * 48)
            result = await pipe.execute()
        if int(result[0]) > self.daily_limit:
            await self.redis.decr(day_key)
            raise DailyLimitExceeded(self.daily_limit)

        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "url": message_url,
            "chat_id": chat_id,
            "status": "queued",
            "created_at": now.isoformat(),
        }
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.hset(JOB_PREFIX + job_id, mapping={k: str(v) for k, v in job.items()})
                pipe.expire(JOB_PREFIX + job_id, 60 * 60 * 24 * 30)
                pipe.zadd(f"fuckjoin:user_jobs:{chat_id}", {job_id: now.timestamp()})
                pipe.rpush(QUEUE_KEY, json.dumps(job, separators=(",", ":")))
                await pipe.execute()
        except Exception:
            await self.redis.decr(day_key)
            raise
        return job

    async def get(self, job_id: str) -> dict[str, str] | None:
        data = await self.redis.hgetall(JOB_PREFIX + job_id)
        return data or None

    async def update(self, job_id: str, **fields: Any) -> None:
        await self.redis.hset(JOB_PREFIX + job_id, mapping={k: str(v) for k, v in fields.items()})

    async def history(self, chat_id: int, limit: int = 10) -> list[dict[str, str]]:
        ids = await self.redis.zrevrange(f"fuckjoin:user_jobs:{chat_id}", 0, max(0, min(limit, 20) - 1))
        if not ids:
            return []
        async with self.redis.pipeline(transaction=False) as pipe:
            for job_id in ids:
                pipe.hgetall(JOB_PREFIX + job_id)
            rows = await pipe.execute()
        return [row for row in rows if row]

    async def quota_used(self, chat_id: int) -> int:
        now = datetime.now(timezone.utc)
        value = await self.redis.get(f"fuckjoin:quota:{chat_id}:{now:%Y%m%d}")
        return int(value or 0)

    async def cancel(self, job_id: str) -> bool:
        data = await self.get(job_id)
        if not data or data.get("status") in {"completed", "failed", "cancelled"}:
            return False
        await self.update(job_id, cancel_requested="1")
        return True
