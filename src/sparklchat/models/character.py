"""Stored characters.

The canonical V2 card JSON is the source of truth (`card_json`); the other
columns are denormalized for listing, sorting, and display.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from sparklchat.models.base import utcnow


class Character(SQLModel, table=True):
    __tablename__ = "characters"

    id: int | None = Field(default=None, primary_key=True)
    # Nullable for characters bundled with the app (sharing arrives later).
    user_id: int | None = Field(
        default=None, foreign_key="users.id", ondelete="CASCADE", index=True
    )
    name: str = Field(index=True)
    spec_version: str = "2.0"
    # Which format the card arrived in: "v1" or "v2".
    source: str = "v2"
    card_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    avatar_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CharacterSummary(SQLModel):
    id: int
    name: str
    spec_version: str
    source: str
    tags: list[str]
    creator: str
    character_version: str
    has_avatar: bool
    created_at: datetime
    updated_at: datetime


class CharacterDetail(CharacterSummary):
    card: dict[str, Any]


class CharacterUpdate(SQLModel):
    """PATCH payload. The card is replaced wholesale when provided."""

    card: dict[str, Any] | None = None
