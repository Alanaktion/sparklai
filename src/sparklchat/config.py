"""Application configuration loaded from the environment and an optional `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Sparkl Chat"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./sparklchat.db"

    # Signing key for auth tokens and future Fernet key derivation for provider
    # API keys at rest. Never ship the default value.
    secret_key: str = "insecure-development-key-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
