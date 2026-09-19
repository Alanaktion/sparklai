"""Password hashing and JWT access-token helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from sparklchat.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash or an over-long password: treat as a failed login.
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed bearer token for `subject` (the user id)."""
    settings = get_settings()
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode a token, raising `jwt.InvalidTokenError` if it is not valid."""
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
