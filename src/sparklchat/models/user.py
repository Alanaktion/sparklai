"""User accounts and their auth-facing request/response schemas."""

from datetime import datetime

from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

from sparklchat.models.base import utcnow

# bcrypt hashes at most 72 bytes of input and newer releases reject longer
# passwords instead of silently truncating them.
BCRYPT_MAX_PASSWORD_BYTES = 72


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    # Stored lowercased so logins are case-insensitive.
    email: str = Field(unique=True, index=True, max_length=320)
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)
    is_active: bool = Field(default=True)


class UserCreate(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes")
        return value


class UserPublic(SQLModel):
    id: int
    email: str
    created_at: datetime
    is_active: bool


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
