from fastapi import FastAPI
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Standalone Telegram automation management API. Engine integration is pending.",
)

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "fuckjoin-pro", "version": "0.1.0"}

@app.get("/api/v1", tags=["system"])
def api_info():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "foundation",
        "telegram_engine": "not_integrated",
        "dashboard": "not_integrated",
    }
