import hmac
import re
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from app.config import settings
from app.jobs.queue import DailyLimitExceeded
from app.jobs.runtime import job_queue

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _auth(value: str | None) -> None:
    if not value or not hmac.compare_digest(value, settings.app_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


class CreateJob(BaseModel):
    message_url: str = Field(min_length=12, max_length=300)
    chat_id: int


@router.post("")
async def create_job(body: CreateJob, x_app_secret: str | None = Header(default=None)):
    _auth(x_app_secret)
    allowed = {int(x) for x in settings.telegram_admin_ids.split(",") if x.strip().isdigit()}
    if body.chat_id not in allowed:
        raise HTTPException(status_code=403, detail="chat_id must be an allow-listed admin Telegram user ID")
    if not re.match(r"^https?://t\.me/", body.message_url.strip()):
        raise HTTPException(status_code=422, detail="Only t.me message links are accepted")
    try:
        from app.jobs.worker import parse_message_link
        parse_message_link(body.message_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return await job_queue.enqueue(body.message_url, body.chat_id)
    except DailyLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=f"Daily job limit reached ({exc.args[0]})") from exc


@router.get("/{job_id}")
async def job_status(job_id: str, x_app_secret: str | None = Header(default=None)):
    _auth(x_app_secret)
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    result = await job_queue.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.delete("/{job_id}")
async def cancel_job(job_id: str, x_app_secret: str | None = Header(default=None)):
    _auth(x_app_secret)
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    if not await job_queue.cancel(job_id):
        raise HTTPException(status_code=409, detail="Job cannot be cancelled")
    return {"id": job_id, "status": "cancellation_requested"}
