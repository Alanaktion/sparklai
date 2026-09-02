"""Port of `src/lib/chat/conversations.ts`. Pure functions operating on anything with `role`/`body`
attributes (in practice, `db.models.Chat` rows) — used by `app/chats/service.py` to separate a
persisted chat history into prior conversation summaries plus the current, live segment."""

from collections.abc import Sequence
from typing import Protocol

CONVERSATION_SUMMARY_PREFIX = "Previous conversation summary:\n"


class ConversationMessage(Protocol):
    role: str
    body: str


def is_conversation_summary_message(message: ConversationMessage) -> bool:
    return message.role == "system" and message.body.startswith(CONVERSATION_SUMMARY_PREFIX)


def build_conversation_summary_body(summary: str) -> str:
    return f"{CONVERSATION_SUMMARY_PREFIX}{summary.strip()}"


def extract_conversation_summary(body: str) -> str:
    if not body.startswith(CONVERSATION_SUMMARY_PREFIX):
        return body.strip()
    return body[len(CONVERSATION_SUMMARY_PREFIX) :].strip()


def partition_chat_history(
    chat_history: Sequence[ConversationMessage],
) -> tuple[list[str], list[ConversationMessage]]:
    """Returns `(previous_summaries, active_messages)` — `active_messages` is reset every time a
    summary marker is encountered, so it ends up holding only the most recent, still-live segment
    of the conversation."""
    previous_summaries: list[str] = []
    active_messages: list[ConversationMessage] = []

    for message in chat_history:
        if is_conversation_summary_message(message):
            previous_summaries.append(extract_conversation_summary(message.body))
            active_messages = []
            continue
        if message.role in ("user", "assistant"):
            active_messages.append(message)

    return previous_summaries, active_messages


def has_active_conversation(chat_history: Sequence[ConversationMessage]) -> bool:
    _, active_messages = partition_chat_history(chat_history)
    return len(active_messages) > 0


def format_conversation_transcript(chat_history: Sequence[ConversationMessage]) -> str:
    lines = [
        f"{'Human' if message.role == 'user' else 'Assistant'}: {message.body}"
        for message in chat_history
        if message.role in ("user", "assistant")
    ]
    return "\n".join(lines)
