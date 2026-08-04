from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/postgres"

    backend_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"

    jwt_secret: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 10080

    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "http://localhost:8000/auth/discord/callback"
    discord_guild_id: str = ""
    discord_bot_token: str = ""

    discord_role_id_tier_1: str = ""
    discord_role_id_tier_2: str = ""
    discord_role_id_tier_3: str = ""

    bot_internal_api_url: str = "http://localhost:8001"
    bot_internal_api_secret: str = ""

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_mode: str = "sandbox"
    paypal_webhook_id: str = ""

    nowpayments_api_key: str = ""
    nowpayments_ipn_secret: str = ""

    admin_discord_ids: str = ""

    @property
    def admin_discord_id_set(self) -> set[str]:
        return {
            discord_id.strip()
            for discord_id in self.admin_discord_ids.split(",")
            if discord_id.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
