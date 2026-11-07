from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.telegram.runtime import session_manager, admin_bot
from app.telegram.router import router as telegram_router
from app.jobs.runtime import job_queue
from app.jobs.router import router as jobs_router
from app.jobs.worker import DownloadWorker

worker = DownloadWorker(settings.redis_url, job_queue, session_manager, settings.telegram_bot_token)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await session_manager.start()
    await admin_bot.start()
    await worker.start()
    try:
        yield
    finally:
        await worker.close()
        await admin_bot.close()
        await session_manager.close()
        await job_queue.close()


app = FastAPI(title=settings.app_name, version="0.5.0",
              description="Self-hosted Telegram media retrieval for chats the account can already access.",
              lifespan=lifespan)
app.include_router(telegram_router)
app.include_router(jobs_router)


@app.get("/health", tags=["system"])
async def health():
    try:
        await job_queue.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "service": "fuckjoin-pro",
            "version": "0.5.0", "redis": redis_ok, "worker": bool(worker.task and not worker.task.done())}


@app.get("/api/v1", tags=["system"])
def api_info():
    return {"name": settings.app_name, "version": "0.5.0", "status": "telegram_admin_bot",
            "telegram_engine": "session_management", "job_queue": "redis", "worker": "accessible_media_download",
            "deep_link_bot_handoffs": "not_supported", "automatic_group_joining": "not_supported"}
