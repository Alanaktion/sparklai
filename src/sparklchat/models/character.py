"""Stored characters.

The canonical card JSON is the source of truth (`card_json`); the other
columns are denormalized for listing, sorting, and display. Cards keep the
format they were imported as (V1/V2 normalise to V2 shape, V3 stays V3).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from sparklchat.models.base import utcnow
from sparklchat.models.hooks import CharacterHooks


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
    # Denormalized from the card so listing and filtering can stay in SQL.
    creator: str = Field(default="", max_length=200, index=True)
    character_version: str = Field(default="", max_length=100)
    # Published characters can be read and chatted with by any user.
    is_public: bool = Field(default=False, index=True)
    card_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    avatar_path: str | None = Field(default=None)
    # A stored CHARX package (or PNG card) with the card's binary assets, kept so a
    # V3 card with assets can be exported losslessly. Null for plain JSON/PNG cards.
    package_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CharacterTag(SQLModel, table=True):
    """Lowercased tags, for case-insensitive filtering.

    The card's `data.tags` remains the source of truth (and keeps the original
    casing); these rows are rebuilt from it whenever a card is written.
    """

    __tablename__ = "character_tags"

    character_id: int = Field(foreign_key="characters.id", ondelete="CASCADE", primary_key=True)
    tag: str = Field(primary_key=True, max_length=100, index=True)


class CharacterSummary(SQLModel):
    id: int
    name: str
    spec_version: str
    source: str
    tags: list[str]
    creator: str
    character_version: str
    is_public: bool
    # Whether the requesting user owns this character.
    is_mine: bool
    has_avatar: bool
    created_at: datetime
    updated_at: datetime


class CharacterDetail(CharacterSummary):
    card: dict[str, Any]
    # Client-side voice hooks declared in the card's `extensions.sparklchat`.
    hooks: CharacterHooks = Field(default_factory=CharacterHooks)
    # Non-fatal import notes, e.g. a card written to a newer spec version.
    warnings: list[str] = Field(default_factory=list)


class CharacterUpdate(SQLModel):
    """PATCH payload. The card is replaced wholesale when provided."""

    card: dict[str, Any] | None = None
    is_public: bool | None = None
