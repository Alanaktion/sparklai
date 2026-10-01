"""Session and message helpers: greetings, swipes, titles, prompt context."""

from collections.abc import Iterable, Mapping, Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.base import utcnow
from sparklchat.models.card import CharacterBook, CharacterCard
from sparklchat.models.character import Character
from sparklchat.models.chat import (
    ChatSession,
    Message,
    MessageImage,
    MessagePublic,
    SessionCharacter,
    SessionCharacterPublic,
)
from sparklchat.models.provider import Provider
from sparklchat.models.user_settings import UserSettings
from sparklchat.services.cards import (
    card_group_greetings,
    card_nickname,
    card_user_icon,
    load_card,
)
from sparklchat.services.generated_images import (
    copy_generated_image,
    delete_generated_image,
    save_generated_image,
)
from sparklchat.services.prompts import (
    CastMember,
    HistoryTurn,
    PromptContext,
    build_prompt,
    substitute_macros,
)
from sparklchat.services.providers import BaseClient, ChatMessage, ProviderError
from sparklchat.services.providers.comfyui import GeneratedImage
from sparklchat.services.tokens import count_tokens

TITLE_MAX_LENGTH = 60
# Cap on stored per-entry match counts, so a long session cannot grow unbounded.
ACTIVATION_LIMIT = 100


def card_of(character: Character) -> CharacterCard:
    return load_card(character.card_json)


def character_name(character: Character) -> str:
    return (character.name or "").strip() or "Character"


async def session_cast(db: AsyncSession, session: ChatSession) -> list[Character]:
    """The session's members, primary first.

    Falls back to the primary character when the session predates the
    `session_characters` table.
    """
    rows = (
        await db.exec(
            select(SessionCharacter)
            .where(SessionCharacter.session_id == session.id)
            .order_by(SessionCharacter.position)
        )
    ).all()
    ids = [row.character_id for row in rows]
    characters: dict[int, Character] = {}
    if ids:
        found = (await db.exec(select(Character).where(Character.id.in_(ids)))).all()
        characters = {character.id: character for character in found if character.id is not None}

    ordered = [characters[character_id] for character_id in ids if character_id in characters]
    if ordered:
        return ordered

    primary = await db.get(Character, session.character_id)
    return [primary] if primary is not None else []


def cast_public(characters: Sequence[Character], primary_id: int) -> list[SessionCharacterPublic]:
    return [
        SessionCharacterPublic(
            id=character.id or 0,
            name=character_name(character),
            has_avatar=bool(character.avatar_path),
            is_primary=character.id == primary_id,
        )
        for character in characters
    ]


def cast_members(characters: Sequence[Character]) -> list[CastMember]:
    return list(cast_by_id(characters).values())


def cast_by_id(characters: Sequence[Character]) -> dict[int, CastMember]:
    """Cast members keyed by character id, so the acting member can reuse the
    same `CastMember` (and therefore the same card object) as the cast list."""
    return {
        character.id: CastMember(name=character_name(character), card=card_of(character))
        for character in characters
        if character.id is not None
    }


def speaker_map(characters: Sequence[Character]) -> dict[int, str]:
    """Character id -> name, for labelling assistant turns in a group chat."""
    return {character.id: character_name(character) for character in characters if character.id}


def prompt_context(card: CharacterCard, settings: UserSettings | None) -> PromptContext:
    user_name = (settings.display_name if settings else "") or "User"
    return PromptContext(
        character_name=card_nickname(card),
        user_name=user_name.strip() or "User",
    )


def swipe_list(message: Message) -> list[str]:
    swipes = (message.meta or {}).get("swipes")
    if not isinstance(swipes, list):
        return []
    return [str(item) for item in swipes]


def message_image_entries(message: Message) -> list[dict]:
    """The raw `meta.images` entries (stored file name + size), for internal use."""
    images = (message.meta or {}).get("images")
    if not isinstance(images, list):
        return []
    return [item for item in images if isinstance(item, dict)]


def message_images(message: Message) -> list[MessageImage]:
    return [
        MessageImage(index=index, width=item.get("width"), height=item.get("height"))
        for index, item in enumerate(message_image_entries(message))
    ]


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
        speaker_id=message.speaker_id,
        images=message_images(message),
    )


async def append_image_message(
    db: AsyncSession,
    session: ChatSession,
    prompt: str,
    images: Sequence[GeneratedImage],
    width: int,
    height: int,
) -> Message:
    """Persist a ComfyUI generation as a message.

    The prompt is the message's text and the generated file(s) are attached via
    `meta.images`; `meta.kind = "image"` marks it as a generated attachment
    rather than character dialogue, since `speaker_id` is left null the same
    way a user/system message would be (see `Message.speaker_id`'s docstring
    on the legacy-row ambiguity of a null value).
    """
    stored = [
        {
            "path": save_generated_image(image.data, image.content_type),
            "width": width,
            "height": height,
        }
        for image in images
    ]
    message = Message(
        session_id=session.id,
        role="assistant",
        content=prompt,
        token_count=count_tokens(prompt),
        meta={"kind": "image", "images": stored},
    )
    db.add(message)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(message)
    return message


def delete_message_images(message: Message) -> None:
    """Remove any files a generated-image message's `meta.images` points at."""
    for entry in message_image_entries(message):
        delete_generated_image(entry.get("path"))


def _duplicate_message_meta(message: Message) -> dict:
    """A copy of `meta`, duplicating any generated-image files it points at so
    the new message's images are independent files (see `copy_generated_image`)."""
    meta = dict(message.meta or {})
    entries = message_image_entries(message)
    if not entries:
        return meta
    copied = []
    for entry in entries:
        path = copy_generated_image(entry.get("path"))
        if path is not None:
            copied.append({**entry, "path": path})
    meta["images"] = copied
    return meta


BRANCH_TITLE_SUFFIX = " (branch)"


def branch_title(title: str, fallback: str) -> str:
    base = (title or fallback).strip() or fallback
    base = base[: TITLE_MAX_LENGTH - len(BRANCH_TITLE_SUFFIX)].rstrip()
    return f"{base}{BRANCH_TITLE_SUFFIX}"


async def duplicate_session(
    db: AsyncSession,
    session: ChatSession,
    characters: Sequence[Character],
    messages: Sequence[Message],
    *,
    title: str,
) -> ChatSession:
    """Create a new session carrying over `session`'s settings and cast, seeded
    with `messages` (a prefix of the original transcript, or all of it for a
    plain duplicate). Used for branching a conversation at a chosen point.
    """
    branch = ChatSession(
        user_id=session.user_id,
        character_id=session.character_id,
        provider_id=session.provider_id,
        title=title,
        system_prompt_override=session.system_prompt_override,
        post_history_override=session.post_history_override,
        use_character_book=session.use_character_book,
        use_world_book=session.use_world_book,
        lorebook_state=dict(session.lorebook_state or {}),
    )
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    for position, character in enumerate(characters):
        if character.id is None:
            continue
        db.add(SessionCharacter(session_id=branch.id, character_id=character.id, position=position))

    for message in messages:
        db.add(
            Message(
                session_id=branch.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                token_count=message.token_count,
                is_greeting=message.is_greeting,
                swipe_index=message.swipe_index,
                speaker_id=message.speaker_id,
                meta=_duplicate_message_meta(message),
            )
        )
    await db.commit()
    await db.refresh(branch)
    return branch


# A handful of recent turns is enough to establish the scene for an
# auto-generated image prompt without ballooning the request.
AUTO_IMAGE_CONTEXT_TURNS = 8
MAX_AUTO_IMAGE_PROMPT_LENGTH = 500

AUTO_IMAGE_PROMPT_SYSTEM = (
    "You write prompts for an AI image generator based on a roleplay conversation. "
    "Read the conversation and reply with ONLY a single line of comma-separated "
    "visual descriptors (subject, appearance, pose or action, setting, lighting, "
    "art style) that illustrate the most recent message. Use the earlier messages "
    "only for context (who/where/what). Do not include dialogue, narration, "
    "character names as prose, quotation marks, or any explanation of what you "
    "are doing -- just the descriptors."
)


async def derive_image_prompt(
    client: BaseClient,
    card: CharacterCard,
    messages: Sequence[Message],
    speakers: Mapping[int, str] | None,
) -> str:
    """Ask the session's text provider to write an image prompt for the latest
    message, using a little recent context so the scene stays consistent.

    Raises `ProviderError` if there is nothing to illustrate yet or the
    provider's reply is unusable, the same way a failed generation would.
    """
    turns = history_turns(messages, speakers)[-AUTO_IMAGE_CONTEXT_TURNS:]
    if not turns:
        raise ProviderError("There is nothing in this conversation to illustrate yet")

    context = [ChatMessage(role="system", content=AUTO_IMAGE_PROMPT_SYSTEM)]
    description = (card.data.description or "").strip()
    if description:
        context.append(
            ChatMessage(role="system", content=f"{card_nickname(card)}'s appearance: {description}")
        )
    context.extend(ChatMessage(role=turn.role, content=turn.content) for turn in turns)

    reply = await client.complete(context)
    prompt = " ".join(reply.split()).strip(" \"'")
    if not prompt:
        raise ProviderError("The provider returned an empty image prompt")
    return prompt[:MAX_AUTO_IMAGE_PROMPT_LENGTH]


def greeting_variants(
    card: CharacterCard, context: PromptContext, *, group: bool = False
) -> list[str]:
    """`first_mes`, `alternate_greetings`, and (in a group) the group greetings.

    Macros are resolved here so the greeting is stored with the character's
    nickname and the user's display name already substituted.
    """
    candidates = [card.data.first_mes, *card.data.alternate_greetings]
    if group:
        candidates.extend(card_group_greetings(card))
    return [substitute_macros(text, context) for text in candidates if text and text.strip()]


async def create_greeting(
    db: AsyncSession,
    session: ChatSession,
    card: CharacterCard,
    context: PromptContext,
    *,
    group: bool = False,
) -> Message | None:
    """Seed a new session with the greeting as the first assistant message."""
    variants = greeting_variants(card, context, group=group)
    if not variants:
        return None

    message = Message(
        session_id=session.id,
        role="assistant",
        content=variants[0],
        is_greeting=True,
        swipe_index=0,
        speaker_id=session.character_id,
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


def history_turns(
    messages: Sequence[Message], speakers: Mapping[int, str] | None = None
) -> list[HistoryTurn]:
    """Chat turns for the prompt.

    When `speakers` is given (a group chat) each assistant turn is prefixed with
    the speaking character's name, so the model can tell the cast apart.
    """
    label = bool(speakers)
    turns: list[HistoryTurn] = []
    for message in messages:
        if message.role not in {"user", "assistant"} or not message.content.strip():
            continue
        content = message.content
        if label and message.role == "assistant":
            name = (speakers or {}).get(message.speaker_id or -1)
            if name:
                content = f"{name}: {content}"
        turns.append(
            HistoryTurn(role=message.role, content=content, is_greeting=message.is_greeting)
        )
    return turns


def active_greeting_index(messages: Sequence[Message]) -> int | None:
    """The swipe index of the session's greeting, for `@@is_greeting`."""
    for message in messages:
        if message.is_greeting:
            return message.swipe_index
    return None


def settings_world_book(settings: UserSettings | None) -> CharacterBook | None:
    """The user's world book, validated, or None when they have not written one."""
    raw = settings.world_book if settings else None
    if not raw:
        return None
    return CharacterBook.model_validate(raw)


def activation_counts(session: ChatSession) -> dict[str, int]:
    """How often each lorebook entry has matched in this session so far."""
    state = (session.lorebook_state or {}).get("matches")
    if not isinstance(state, dict):
        return {}
    return {
        str(key): int(value)
        for key, value in state.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def record_activations(session: ChatSession, keys: Iterable[str]) -> None:
    """Bump the match counts for the entries that matched this turn."""
    counts = activation_counts(session)
    for key in keys:
        counts[key] = min(counts.get(key, 0) + 1, ACTIVATION_LIMIT)
    session.lorebook_state = {**(session.lorebook_state or {}), "matches": counts}


def build_session_prompt(
    *,
    card: CharacterCard,
    session: ChatSession,
    messages: Sequence[Message],
    settings: UserSettings | None,
    context_window: int,
    context_reserve: int,
    cast: Sequence[CastMember] | None = None,
    speakers: Mapping[int, str] | None = None,
    activation_counts: Mapping[str, int] | None = None,
    matched_keys: set[str] | None = None,
) -> list[ChatMessage]:
    user_icon = card_user_icon(card)
    return build_prompt(
        card,
        history_turns(messages, speakers),
        context=prompt_context(card, settings),
        default_system_prompt=settings.default_system_prompt if settings else "",
        default_post_history=settings.default_ujb if settings else "",
        system_prompt_override=session.system_prompt_override,
        post_history_override=session.post_history_override,
        use_character_book=session.use_character_book,
        world_book=settings_world_book(settings),
        use_world_book=session.use_world_book,
        cast=cast,
        context_window=context_window,
        context_reserve=context_reserve,
        greeting_index=active_greeting_index(messages),
        user_icon=user_icon.name if user_icon is not None else None,
        activation_counts=activation_counts,
        matched_keys=matched_keys,
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
