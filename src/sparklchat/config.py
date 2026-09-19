"""Application configuration loaded from the environment and an optional `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
# Where `npm run build` in `frontend/` puts the static SPA.
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "build"
# Where uploaded character avatars are written.
AVATAR_DIR = PROJECT_ROOT / "data" / "avatars"


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

    # Signing key for auth tokens. Also the default source of the encryption key
    # for provider API keys at rest — never ship the default value.
    secret_key: str = "insecure-development-key-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7

    # Optional Fernet key (44 url-safe base64 characters) for encrypting provider
    # API keys. When unset, a key is derived from `secret_key`.
    encryption_key: str | None = None

    # Built Svelte app served by FastAPI. When this directory does not exist the
    # app serves the API alone and logs a hint.
    frontend_dist_dir: Path = FRONTEND_DIST_DIR

    # Directory holding uploaded character avatars.
    avatar_dir: Path = AVATAR_DIR


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
