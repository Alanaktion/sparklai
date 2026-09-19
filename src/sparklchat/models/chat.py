"""Chat sessions and messages.

`metadata` is reserved by SQLAlchemy's declarative base, so the JSON bag for
extra message data (currently the swipe alternatives) is stored as `meta`.
"""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from sparklchat.models.base import utcnow

MessageRole = Literal["system", "user", "assistant"]
SwipeDirection = Literal["next", "prev"]


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    # The primary character: it owns the greeting, the title fallback, and the
    # session's place in a character's session list. Group members beyond it live
    # in `session_characters`.
    character_id: int = Field(foreign_key="characters.id", ondelete="CASCADE", index=True)
    # Null falls back to the user's default provider.
    provider_id: int | None = Field(default=None, foreign_key="providers.id", ondelete="SET NULL")
    title: str = Field(default="", max_length=200)
    # Optional per-session replacements for the character's prompts.
    system_prompt_override: str | None = Field(default=None)
    post_history_override: str | None = Field(default=None)
    use_character_book: bool = Field(default=True)
    use_world_book: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SessionCharacter(SQLModel, table=True):
    """The ordered cast of a session.

    Every session has a row for its primary character too, so the cast can be read
    without falling back to `chat_sessions.character_id`.
    """

    __tablename__ = "session_characters"

    session_id: int = Field(foreign_key="chat_sessions.id", ondelete="CASCADE", primary_key=True)
    character_id: int = Field(foreign_key="characters.id", ondelete="CASCADE", primary_key=True)
    position: int = Field(default=0)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id", ondelete="CASCADE", index=True)
    role: str = Field(default="user", max_length=16)
    content: str = Field(default="")
    created_at: datetime = Field(default_factory=utcnow)
    token_count: int | None = Field(default=None)
    is_greeting: bool = Field(default=False)
    swipe_index: int = Field(default=0)
    # Which character said an assistant line. Null for user/system messages, and
    # for legacy rows, where the session's primary character is implied.
    speaker_id: int | None = Field(default=None, foreign_key="characters.id", ondelete="SET NULL")
    meta: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("meta", JSON, nullable=False)
    )


class MessagePublic(SQLModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime
    is_greeting: bool
    swipe_index: int
    swipe_count: int
    speaker_id: int | None


class MessagePair(SQLModel):
    user: MessagePublic
    assistant: MessagePublic


class RegenerateResult(SQLModel):
    assistant: MessagePublic


class SessionSummary(SQLModel):
    id: int
    character_id: int
    title: str
    provider_id: int | None
    use_character_book: bool
    use_world_book: bool
    created_at: datetime
    updated_at: datetime


class SessionCharacterPublic(SQLModel):
    """A member of a session's cast, for the chat UI."""

    id: int
    name: str
    has_avatar: bool
    is_primary: bool


class SessionDetail(SessionSummary):
    system_prompt_override: str | None
    post_history_override: str | None
    characters: list[SessionCharacterPublic]
    messages: list[MessagePublic]


class SessionCreate(SQLModel):
    title: str | None = Field(default=None, max_length=200)
    provider_id: int | None = None
    # Group members to add alongside the primary character. Duplicates and the
    # primary itself are ignored.
    character_ids: list[int] = Field(default_factory=list)


class SessionUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=200)
    provider_id: int | None = None
    system_prompt_override: str | None = None
    post_history_override: str | None = None
    use_character_book: bool | None = None
    use_world_book: bool | None = None


class MessageCreate(SQLModel):
    content: str = Field(min_length=1)
    # Which cast member should reply. Defaults to the session's primary character.
    speaker_id: int | None = None


class MessageUpdate(SQLModel):
    content: str = Field(min_length=1)


class SwipeRequest(SQLModel):
    direction: SwipeDirection = "next"
