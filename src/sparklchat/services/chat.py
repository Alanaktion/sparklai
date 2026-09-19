"""Session and message helpers: greetings, swipes, titles, prompt context."""

from collections.abc import Sequence

from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.card import TavernCardV2
from sparklchat.models.chat import ChatSession, Message, MessagePublic
from sparklchat.models.provider import Provider
from sparklchat.models.user_settings import UserSettings
from sparklchat.services.prompts import (
    HistoryTurn,
    PromptContext,
    build_prompt,
    substitute_macros,
)
from sparklchat.services.providers import ChatMessage
from sparklchat.services.tokens import count_tokens

TITLE_MAX_LENGTH = 60


def prompt_context(card: TavernCardV2, settings: UserSettings | None) -> PromptContext:
    user_name = (settings.display_name if settings else "") or "User"
    return PromptContext(
        character_name=(card.data.name or "").strip() or "Character",
        user_name=user_name.strip() or "User",
    )


def swipe_list(message: Message) -> list[str]:
    swipes = (message.meta or {}).get("swipes")
    if not isinstance(swipes, list):
        return []
    return [str(item) for item in swipes]


def message_public(message: Message) -> MessagePublic:
    return MessagePublic(
        id=message.id or 0,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        is_greeting=message.is_greeting,
        swipe_index=message.swipe_index,
        swipe_count=max(1, len(swipe_list(message))),
    )


def greeting_variants(card: TavernCardV2, context: PromptContext) -> list[str]:
    """`first_mes` plus `alternate_greetings`, with macros resolved."""
    candidates = [card.data.first_mes, *card.data.alternate_greetings]
    return [substitute_macros(text, context) for text in candidates if text and text.strip()]


async def create_greeting(
    db: AsyncSession, session: ChatSession, card: TavernCardV2, context: PromptContext
) -> Message | None:
    """Seed a new session with the greeting as the first assistant message."""
    variants = greeting_variants(card, context)
    if not variants:
        return None

    message = Message(
        session_id=session.id,
        role="assistant",
        content=variants[0],
        is_greeting=True,
        swipe_index=0,
        meta={"swipes": variants},
        token_count=count_tokens(variants[0]),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


def swipe_message(message: Message, direction: str) -> bool:
    """Cycle the active variant. Returns False when there is nothing to cycle."""
    swipes = swipe_list(message)
    if len(swipes) < 2:
        return False
    step = 1 if direction == "next" else -1
    index = (message.swipe_index + step) % len(swipes)
    message.swipe_index = index
    message.content = swipes[index]
    message.token_count = count_tokens(message.content)
    return True


def record_swipe(message: Message, content: str) -> None:
    """Append a freshly generated alternative and make it the active one."""
    swipes = swipe_list(message)
    if not swipes:
        # First regeneration: keep the original so it can be swiped back to.
        swipes = [message.content]
    swipes.append(content)
    message.meta = {**(message.meta or {}), "swipes": swipes}
    message.swipe_index = len(swipes) - 1
    message.content = content
    message.token_count = count_tokens(content)


def replace_active_content(message: Message, content: str) -> None:
    """Edit the visible text, keeping any recorded alternatives in sync."""
    message.content = content
    message.token_count = count_tokens(content)
    swipes = swipe_list(message)
    if swipes and 0 <= message.swipe_index < len(swipes):
        swipes[message.swipe_index] = content
        message.meta = {**(message.meta or {}), "swipes": swipes}


def history_turns(messages: Sequence[Message]) -> list[HistoryTurn]:
    return [
        HistoryTurn(role=message.role, content=message.content, is_greeting=message.is_greeting)
        for message in messages
        if message.role in {"user", "assistant"} and message.content.strip()
    ]


def build_session_prompt(
    *,
    card: TavernCardV2,
    session: ChatSession,
    messages: Sequence[Message],
    settings: UserSettings | None,
    context_window: int,
    context_reserve: int,
) -> list[ChatMessage]:
    return build_prompt(
        card,
        history_turns(messages),
        context=prompt_context(card, settings),
        default_system_prompt=settings.default_system_prompt if settings else "",
        default_post_history=settings.default_ujb if settings else "",
        system_prompt_override=session.system_prompt_override,
        post_history_override=session.post_history_override,
        use_character_book=session.use_character_book,
        context_window=context_window,
        context_reserve=context_reserve,
    )


def title_from_message(content: str, fallback: str) -> str:
    text = " ".join(content.split())
    if not text:
        return fallback
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    return text[:TITLE_MAX_LENGTH].rstrip() + "…"


async def resolve_provider(db: AsyncSession, session: ChatSession, user_id: int) -> Provider | None:
    """The session's provider, else the user's default, else nothing."""
    provider_id = session.provider_id
    if provider_id is None:
        settings = await db.get(UserSettings, user_id)
        provider_id = settings.default_provider_id if settings is not None else None
    if provider_id is None:
        return None
    provider = await db.get(Provider, provider_id)
    if provider is None or provider.user_id != user_id:
        return None
    return provider
