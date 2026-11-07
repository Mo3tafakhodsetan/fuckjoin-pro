import hmac
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from app.config import settings
from app.telegram.runtime import session_manager

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


def require_app_secret(value: str | None) -> None:
    if not value or not hmac.compare_digest(value, settings.app_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


class SendCodeRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)


class SignInRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    password: str | None = Field(default=None, max_length=256)


@router.get("/session")
async def session_status(x_app_secret: str | None = Header(default=None)):
    require_app_secret(x_app_secret)
    return await session_manager.status()


@router.post("/login/send-code")
async def send_code(body: SendCodeRequest, x_app_secret: str | None = Header(default=None)):
    require_app_secret(x_app_secret)
    try:
        return await session_manager.send_code(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login/verify")
async def verify_code(body: SignInRequest, x_app_secret: str | None = Header(default=None)):
    require_app_secret(x_app_secret)
    try:
        return await session_manager.sign_in(body.code, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/logout")
async def logout(x_app_secret: str | None = Header(default=None)):
    require_app_secret(x_app_secret)
    return await session_manager.logout()
