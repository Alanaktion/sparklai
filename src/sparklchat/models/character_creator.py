"""Request/response schemas for the interactive character-creator assistant.

Nothing here is persisted: the conversation and the in-progress draft card both
live in the browser, and are sent back in full on every turn (the same
stateless shape `CompletionRequest` uses for a one-off provider completion).
"""

from typing import Any, Literal

from sqlmodel import Field, SQLModel

CreatorRole = Literal["user", "assistant"]


class CreatorTurn(SQLModel):
    role: CreatorRole
    content: str


class CreatorMessageRequest(SQLModel):
    # Omitted: falls back to the user's default provider, same as a chat session.
    provider_id: int | None = None
    # The card JSON built up so far (V2 shape), or `{}` before the first reply.
    draft: dict[str, Any] = Field(default_factory=dict)
    # The full conversation so far, ending with the newest user turn.
    messages: list[CreatorTurn] = Field(min_length=1)


class CreatorMessageResult(SQLModel):
    """The non-streaming shape of a reply; the `/message/stream` SSE events
    (`delta`, `message`, `draft`, `error`, `done`) carry the same two fields."""

    message: str
    draft: dict[str, Any]
