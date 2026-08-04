from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Bot configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    discord_bot_token: str = ""
    discord_log_channel_id: str = ""

    bot_internal_api_host: str = "0.0.0.0"
    bot_internal_api_port: int = 8001
    bot_internal_api_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
