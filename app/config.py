from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "FuckJoin Pro"
    app_env: str = "production"
    app_port: int = 8787
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    app_secret: str
    telegram_bot_token: str = ""
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_admin_ids: str = ""
    daily_job_limit: int = 20
    telegram_session_path: str = "/data/telegram.session"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
