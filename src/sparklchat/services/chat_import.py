"""Import chat transcripts from JSON files.

Two shapes are recognised:

* this app's own JSON export (`GET /api/sessions/{id}/export?format=json`), which
  wraps normalised messages in a `session` header plus a `characters` cast, and
* the plain message list other roleplay clients write, where each entry carries
  its body under one of `msg`/`mes`/`content`/`text` and enough context to tell
  who spoke — a `role`, an `is_user` flag, or a `userId`/`characterId` pair.

Parsing is pure: it returns an `ImportedChat` of roles, bodies, and speaker names
for the caller to resolve against the importing user's own characters.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Body fields. `content` first, then the older client spellings.
_CONTENT_KEYS = ("content", "msg", "mes", "text", "message")
# Display names. `name` comes first because `handle` is sometimes a bare username.
_NAME_KEYS = ("name", "handle", "sender", "speaker", "character_name", "author")
_TIME_KEYS = ("created_at", "createdAt", "send_date", "timestamp", "time", "date")
_ROLE_ALIASES = {
    "assistant": "assistant",
    "bot": "assistant",
    "char": "assistant",
    "character": "assistant",
    "human": "user",
    "system": "system",
    "user": "user",
}


class ChatImportError(ValueError):
    """The uploaded file is not a chat transcript we can read."""


@dataclass(slots=True)
class ImportedMessage:
    role: str
    content: str
    created_at: datetime | None = None
    is_greeting: bool = False
    # The speaking character's name on an assistant line, when the file names one.
    speaker: str | None = None


@dataclass(slots=True)
class ImportedChat:
    title: str
    messages: list[ImportedMessage]
    # The other characters the transcript involves, primary excluded.
    character_names: list[str] = field(default_factory=list)


def parse_chat(payload: Any) -> ImportedChat:
    """Turn a decoded JSON chat file into an `ImportedChat`."""
    if not isinstance(payload, dict):
        raise ChatImportError("chat file must be a JSON object")
    if isinstance(payload.get("session"), dict) and isinstance(payload.get("messages"), list):
        return _parse_export(payload)
    return _parse_message_list(payload)


def _parse_export(payload: dict[str, Any]) -> ImportedChat:
    """A transcript this app wrote: `{session, character, characters, messages}`."""
    session = payload["session"]
    cast = [entry for entry in payload.get("characters") or [] if isinstance(entry, dict)]
    # The export's `speaker_id` values are ids from the exporting instance, so they
    # are only meaningful through this file's own cast list.
    names = {
        entry["id"]: _text(entry.get("name")) for entry in cast if isinstance(entry.get("id"), int)
    }

    parsed: list[ImportedMessage] = []
    for raw in payload["messages"]:
        message = _message(raw)
        if message is None:
            continue
        if message.role == "assistant" and isinstance(raw, dict):
            message.speaker = names.get(raw.get("speaker_id")) or message.speaker
        parsed.append(message)

    if not parsed:
        raise ChatImportError("no messages found in the file")

    primary = payload.get("character")
    primary_name = _text(primary.get("name")) if isinstance(primary, dict) else ""
    others: list[str] = []
    for entry in cast:
        if entry.get("is_primary"):
            continue
        name = _text(entry.get("name"))
        if name and name.casefold() != primary_name.casefold() and name not in others:
            others.append(name)
    return ImportedChat(
        title=_text(session.get("title")) or primary_name,
        messages=parsed,
        character_names=others,
    )


def _parse_message_list(payload: dict[str, Any]) -> ImportedChat:
    """A bare transcript: a message array plus a little metadata."""
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list):
        raw_messages = payload.get("chat")
    if not isinstance(raw_messages, list):
        raise ChatImportError("no messages found in the file")

    messages = [message for raw in raw_messages if (message := _message(raw)) is not None]
    if not messages:
        raise ChatImportError("no messages found in the file")
    messages = _in_time_order(messages)
    _mark_greeting(messages, _first(payload, ("greeting", "first_mes")))

    title = _text(_first(payload, ("title", "name", "chat_name")))
    return ImportedChat(title=title, messages=messages)


def _message(raw: Any) -> ImportedMessage | None:
    """One stored message, or None when the entry carries no usable body."""
    if not isinstance(raw, dict):
        return None
    content = _first(raw, _CONTENT_KEYS)
    if not isinstance(content, str) or not content.strip():
        return None
    return ImportedMessage(
        role=_role(raw) or "assistant",
        content=content.strip(),
        created_at=_timestamp(_first(raw, _TIME_KEYS)),
        is_greeting=raw.get("is_greeting") is True,
        speaker=_name(raw),
    )


def _role(raw: dict[str, Any]) -> str | None:
    """The message's role, from whichever convention the file uses."""
    if raw.get("is_system") is True:
        return "system"
    is_user = raw.get("is_user")
    if isinstance(is_user, bool):
        return "user" if is_user else "assistant"
    role = raw.get("role")
    if isinstance(role, str) and role.strip().lower() in _ROLE_ALIASES:
        return _ROLE_ALIASES[role.strip().lower()]
    # Newer card clients mark the speaker with a `userId` or `characterId`.
    if _identifier(raw, "userId", "user_id"):
        return "user"
    if _identifier(raw, "characterId", "character_id"):
        return "assistant"
    return None


def _in_time_order(messages: list[ImportedMessage]) -> list[ImportedMessage]:
    """Sort by timestamp when every message has one; otherwise keep file order."""
    if any(message.created_at is None for message in messages):
        return messages
    # Python's sort is stable, so messages sharing a timestamp keep their order.
    return sorted(messages, key=lambda message: message.created_at)


def _mark_greeting(messages: list[ImportedMessage], greeting: Any) -> None:
    """Flag the greeting line, adding it back when the file kept it separate.

    Files usually repeat the greeting as the first message, so an exact (whitespace
    insensitive) match wins rather than duplicating the opening.
    """
    text = _text(greeting)
    if not text:
        return
    wanted = _collapse(text)
    for message in messages:
        if message.role == "assistant" and _collapse(message.content) == wanted:
            message.is_greeting = True
            return
    messages.insert(0, ImportedMessage(role="assistant", content=text, is_greeting=True))


def _first(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None


def _identifier(raw: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, int) and not isinstance(value, bool):
            return True
    return False


def _name(raw: dict[str, Any]) -> str | None:
    value = _first(raw, _NAME_KEYS)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _timestamp(value: Any) -> datetime | None:
    """A UTC datetime from an ISO 8601 string, or an epoch seconds/milliseconds."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        # Milliseconds are common; the magnitude separates them from seconds.
        seconds = value / 1000 if abs(value) > 100_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # Some clients stringify the epoch instead of formatting an ISO date.
        if len(text) >= 10 and text.replace(".", "").isdigit():
            return _timestamp(float(text))
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
