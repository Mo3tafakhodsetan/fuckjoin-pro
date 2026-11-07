from app.config import settings
from app.telegram.session import TelegramSessionManager
from app.telegram.bot import AdminBot
from app.jobs.runtime import job_queue

session_manager = TelegramSessionManager(
    api_id=settings.telegram_api_id,
    api_hash=settings.telegram_api_hash,
    session_path=settings.telegram_session_path,
)
admin_bot = AdminBot(
    token=settings.telegram_bot_token,
    admin_ids=settings.telegram_admin_ids,
    sessions=session_manager,
    jobs=job_queue,
)
