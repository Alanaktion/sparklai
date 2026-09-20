"""Chat sessions, messages, streamed generation, regeneration, and swipes."""

import json
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import func
from sqlmodel import select

from sparklchat.api.access import readable_character
from sparklchat.api.deps import CurrentUserDep
from sparklchat.config import get_settings
from sparklchat.db import SessionDep
from sparklchat.models.base import utcnow
from sparklchat.models.card import CharacterCard
from sparklchat.models.character import Character
from sparklchat.models.chat import (
    ChatSession,
    Message,
    MessageCreate,
    MessagePair,
    MessagePublic,
    MessageUpdate,
    RegenerateResult,
    SessionCharacter,
    SessionCreate,
    SessionDetail,
    SessionListItem,
    SessionSummary,
    SessionUpdate,
    SwipeRequest,
)
from sparklchat.models.provider import Provider
from sparklchat.models.user_settings import UserSettings
from sparklchat.services.cards import load_card
from sparklchat.services.chat import (
    activation_counts,
    build_session_prompt,
    cast_by_id,
    cast_public,
    character_name,
    create_greeting,
    message_public,
    prompt_context,
    record_activations,
    record_swipe,
    replace_active_content,
    resolve_provider,
    session_cast,
    speaker_map,
    swipe_message,
    title_from_message,
)
from sparklchat.services.chat_import import ChatImportError, parse_chat
from sparklchat.services.crypto import EncryptionError
from sparklchat.services.downloads import attachment_headers, download_filename
from sparklchat.services.prompts import CastMember
from sparklchat.services.providers import (
    BaseClient,
    ProviderError,
    api_key_for,
    build_client,
    config_for,
)
from sparklchat.services.tokens import count_tokens
from sparklchat.services.user_settings import get_or_create_settings

router = APIRouter(prefix="/sessions", tags=["chat"])
character_router = APIRouter(prefix="/characters", tags=["chat"])

_NO_PROVIDER = "No provider configured. Add one under Settings and make it your default."
# How much of the latest message the dashboard preview keeps.
PREVIEW_LENGTH = 160
# Imported transcripts are small text files; anything bigger is a mistake.
MAX_IMPORT_BYTES = 8 * 1024 * 1024


async def _owned_session(db: SessionDep, session_id: int, user_id: int) -> ChatSession:
    statement = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user_id
    )
    session = (await db.exec(statement)).first()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


async def _owned_provider(db: SessionDep, provider_id: int, user_id: int) -> Provider:
    statement = select(Provider).where(Provider.id == provider_id, Provider.user_id == user_id)
    provider = (await db.exec(statement)).first()
    if provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    return provider


async def _load_messages(db: SessionDep, session_id: int) -> list[Message]:
    statement = select(Message).where(Message.session_id == session_id).order_by(Message.id)
    return list((await db.exec(statement)).all())


def _preview(content: str) -> str:
    """Collapse whitespace and clip to a single-line preview."""
    text = " ".join(content.split())
    if len(text) <= PREVIEW_LENGTH:
        return text
    return text[: PREVIEW_LENGTH - 1].rstrip() + "\u2026"


async def _last_messages(db: SessionDep, session_ids: list[int]) -> dict[int, str]:
    """The newest message per session, keyed by session id."""
    if not session_ids:
        return {}
    newest = (
        select(Message.session_id, func.max(Message.id).label("message_id"))
        .where(Message.session_id.in_(session_ids))
        .group_by(Message.session_id)
        .subquery()
    )
    rows = (await db.exec(select(Message).join(newest, Message.id == newest.c.message_id))).all()
    return {row.session_id: row.content for row in rows}


def _summary(session: ChatSession) -> SessionSummary:
    return SessionSummary(
        id=session.id or 0,
        character_id=session.character_id,
        title=session.title,
        provider_id=session.provider_id,
        use_character_book=session.use_character_book,
        use_world_book=session.use_world_book,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _detail(
    session: ChatSession, characters: list[Character], messages: list[Message]
) -> SessionDetail:
    return SessionDetail(
        **_summary(session).model_dump(),
        system_prompt_override=session.system_prompt_override,
        post_history_override=session.post_history_override,
        characters=cast_public(characters, session.character_id),
        messages=[message_public(message) for message in messages],
    )


def _client_for(provider: Provider) -> BaseClient:
    try:
        api_key = api_key_for(provider)
    except EncryptionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    try:
        return build_client(config_for(provider, api_key))
    except ProviderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@dataclass(slots=True)
class _Generation:
    """Everything needed to build a prompt and call the provider."""

    session: ChatSession
    characters: list[Character]
    acting: Character
    card: CharacterCard
    members: list[CastMember]
    speakers: dict[int, str]
    settings: UserSettings
    client: BaseClient


def _pick_speaker(
    characters: list[Character], session: ChatSession, speaker_id: int | None
) -> Character:
    """The character who should reply: the requested one, else the primary."""
    if not characters:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    if speaker_id is None:
        return next(
            (member for member in characters if member.id == session.character_id),
            characters[0],
        )
    for member in characters:
        if member.id == speaker_id:
            return member
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "speaker_id must be one of this session's characters",
    )


async def _generation_context(
    db: SessionDep, session_id: int, user_id: int, speaker_id: int | None = None
) -> _Generation:
    session = await _owned_session(db, session_id, user_id)
    characters = await session_cast(db, session)
    acting = _pick_speaker(characters, session, speaker_id)
    members_by_id = cast_by_id(characters)
    member = members_by_id.get(acting.id or -1)
    if member is None:  # pragma: no cover - the cast always contains the acting member
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    settings = await get_or_create_settings(db, user_id)

    provider = await resolve_provider(db, session, user_id)
    if provider is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _NO_PROVIDER)

    speakers = speaker_map(characters) if len(characters) > 1 else {}
    return _Generation(
        session=session,
        characters=characters,
        acting=acting,
        card=member.card,
        members=list(members_by_id.values()),
        speakers=speakers,
        settings=settings,
        client=_client_for(provider),
    )


def _prompt(generation: _Generation, messages: list[Message]):
    settings_values = get_settings()
    matched_keys: set[str] = set()
    prompt = build_session_prompt(
        card=generation.card,
        session=generation.session,
        messages=messages,
        settings=generation.settings,
        context_window=settings_values.context_window,
        context_reserve=settings_values.context_reserve,
        cast=generation.members,
        speakers=generation.speakers or None,
        activation_counts=activation_counts(generation.session),
        matched_keys=matched_keys,
    )
    # The session row is committed alongside the reply, so the counters stick.
    if matched_keys:
        record_activations(generation.session, matched_keys)
    return prompt


async def _append_user_message(
    db: SessionDep, session: ChatSession, character: Character, content: str
) -> Message:
    prior = (
        await db.exec(
            select(Message.id)
            .where(Message.session_id == session.id, Message.role == "user")
            .limit(1)
        )
    ).first()

    message = Message(
        session_id=session.id, role="user", content=content, token_count=count_tokens(content)
    )
    db.add(message)
    if prior is None:
        # Auto-title from the first thing the user says.
        session.title = title_from_message(content, session.title or character.name)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(message)
    return message


async def _append_assistant_message(
    db: SessionDep, session: ChatSession, content: str, speaker_id: int | None = None
) -> Message:
    message = Message(
        session_id=session.id,
        role="assistant",
        content=content,
        token_count=count_tokens(content),
        speaker_id=speaker_id,
    )
    db.add(message)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(message)
    return message


def _event(name: str, payload: dict) -> ServerSentEvent:
    return ServerSentEvent(data=payload, event=name)


@character_router.get("/{character_id}/sessions")
async def list_sessions(
    character_id: int, db: SessionDep, current_user: CurrentUserDep
) -> list[SessionSummary]:
    await readable_character(db, character_id, current_user.id)
    statement = (
        select(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.character_id == character_id,
        )
        .order_by(ChatSession.updated_at.desc())
    )
    return [_summary(row) for row in (await db.exec(statement)).all()]


@router.get("")
async def list_recent_sessions(
    db: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SessionListItem]:
    """The user's most recently active sessions, across every character."""
    statement = (
        select(ChatSession, Character)
        .join(Character, ChatSession.character_id == Character.id)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .limit(limit)
    )
    rows = (await db.exec(statement)).all()
    previews = await _last_messages(db, [session.id for session, _ in rows])
    return [
        SessionListItem(
            **_summary(session).model_dump(),
            character_name=character_name(character),
            character_has_avatar=bool(character.avatar_path),
            last_message=_preview(previews[session.id]) if session.id in previews else None,
        )
        for session, character in rows
    ]


@character_router.post("/{character_id}/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    character_id: int,
    payload: SessionCreate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> SessionDetail:
    """Start a session and seed it with the primary character's greeting.

    `character_ids` adds group members; the path character stays primary and the
    greeting still comes from it.
    """
    character = await readable_character(db, character_id, current_user.id)
    if payload.provider_id is not None:
        await _owned_provider(db, payload.provider_id, current_user.id)

    characters = [character]
    for member_id in payload.character_ids:
        if member_id == character_id or any(item.id == member_id for item in characters):
            continue
        characters.append(await readable_character(db, member_id, current_user.id))

    card = load_card(character.card_json)
    settings = await get_or_create_settings(db, current_user.id)

    session = ChatSession(
        user_id=current_user.id,
        character_id=character_id,
        provider_id=payload.provider_id,
        title=(payload.title or "").strip() or character.name,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    for position, member in enumerate(characters):
        db.add(SessionCharacter(session_id=session.id, character_id=member.id, position=position))
    await db.commit()

    greeting = await create_greeting(
        db, session, card, prompt_context(card, settings), group=len(characters) > 1
    )
    messages = [greeting] if greeting is not None else []
    return _detail(session, characters, messages)


async def _import_cast(
    db: SessionDep, primary: Character, names: list[str], user_id: int
) -> list[Character]:
    """The primary character, plus any of the user's own that the file names.

    A SparklChat export carries its cast by name, so a group transcript keeps its
    speakers (and the name-based `speaker_id` mapping) without the user having to
    pick the cast again. Matching is limited to the user's own characters.
    """
    wanted = {name.casefold() for name in names if name.strip()}
    wanted.discard(character_name(primary).casefold())
    if not wanted:
        return [primary]

    rows = (await db.exec(select(Character).where(Character.user_id == user_id))).all()
    by_name = {character_name(row).casefold(): row for row in rows}
    members = [primary]
    seen = {primary.id}
    for name in names:
        member = by_name.get(name.strip().casefold())
        if member is None or member.id in seen:
            continue
        seen.add(member.id)
        members.append(member)
    return members


@character_router.post("/{character_id}/sessions/import", status_code=status.HTTP_201_CREATED)
async def import_session(
    character_id: int,
    file: Annotated[UploadFile, File()],
    db: SessionDep,
    current_user: CurrentUserDep,
) -> SessionDetail:
    """Import a JSON transcript as a new session for this character.

    Accepts this app's own export and the message-list JSON other clients write.
    The path character is the session's primary; a transcript that names other
    characters adds any of the user's own with a matching name, so a group chat
    keeps its speakers. The transcript's own timestamps are kept, so imported
    history lands where it belongs on the dashboard.
    """
    character = await readable_character(db, character_id, current_user.id)
    data = await file.read()
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large")

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Could not read the file: {exc}"
        ) from exc
    try:
        chat = parse_chat(payload)
    except ChatImportError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    characters = await _import_cast(db, character, chat.character_names, current_user.id)
    speakers = {character_name(member).casefold(): member.id for member in characters}
    times = [message.created_at for message in chat.messages if message.created_at is not None]
    now = utcnow()

    session = ChatSession(
        user_id=current_user.id,
        character_id=character_id,
        title=(chat.title or character.name)[:200] or character.name,
        created_at=min(times) if times else now,
        updated_at=max(times) if times else now,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    for position, member in enumerate(characters):
        db.add(SessionCharacter(session_id=session.id, character_id=member.id, position=position))
    await db.commit()

    stored: list[Message] = []
    previous = session.created_at
    for item in chat.messages:
        when = item.created_at or previous
        previous = when
        speaker_id = None
        if item.role == "assistant":
            speaker_id = speakers.get((item.speaker or "").casefold(), character_id)
        message = Message(
            session_id=session.id,
            role=item.role,
            content=item.content,
            created_at=when,
            # Only an assistant line can be the seeded greeting.
            is_greeting=item.is_greeting and item.role == "assistant",
            speaker_id=speaker_id,
            token_count=count_tokens(item.content),
        )
        db.add(message)
        stored.append(message)
    await db.commit()
    return _detail(session, characters, stored)


@router.get("/{session_id}")
async def get_session(
    session_id: int, db: SessionDep, current_user: CurrentUserDep
) -> SessionDetail:
    session = await _owned_session(db, session_id, current_user.id)
    characters = await session_cast(db, session)
    return _detail(session, characters, await _load_messages(db, session.id))


@router.patch("/{session_id}")
async def update_session(
    session_id: int,
    payload: SessionUpdate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> SessionDetail:
    session = await _owned_session(db, session_id, current_user.id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("title") is not None:
        session.title = data["title"]
    if "provider_id" in data:
        if data["provider_id"] is not None:
            await _owned_provider(db, data["provider_id"], current_user.id)
        session.provider_id = data["provider_id"]
    if "system_prompt_override" in data:
        session.system_prompt_override = data["system_prompt_override"]
    if "post_history_override" in data:
        session.post_history_override = data["post_history_override"]
    if data.get("use_character_book") is not None:
        session.use_character_book = data["use_character_book"]
    if data.get("use_world_book") is not None:
        session.use_world_book = data["use_world_book"]

    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    characters = await session_cast(db, session)
    return _detail(session, characters, await _load_messages(db, session.id))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: int, db: SessionDep, current_user: CurrentUserDep) -> None:
    session = await _owned_session(db, session_id, current_user.id)
    await db.delete(session)
    await db.commit()


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: int, db: SessionDep, current_user: CurrentUserDep
) -> list[MessagePublic]:
    session = await _owned_session(db, session_id, current_user.id)
    return [message_public(row) for row in await _load_messages(db, session.id)]


@router.post("/{session_id}/messages")
async def send_message(
    session_id: int,
    payload: MessageCreate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> MessagePair:
    generation = await _generation_context(db, session_id, current_user.id, payload.speaker_id)
    user_message = await _append_user_message(
        db, generation.session, generation.acting, payload.content
    )

    prompt = _prompt(generation, await _load_messages(db, generation.session.id))
    try:
        reply = await generation.client.complete(prompt)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    assistant_message = await _append_assistant_message(
        db, generation.session, reply, generation.acting.id
    )
    return MessagePair(
        user=message_public(user_message),
        assistant=message_public(assistant_message),
    )


@router.post("/{session_id}/messages/stream", response_class=EventSourceResponse)
async def stream_message(
    session_id: int,
    payload: MessageCreate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> AsyncIterable[ServerSentEvent]:
    generation = await _generation_context(db, session_id, current_user.id, payload.speaker_id)
    user_message = await _append_user_message(
        db, generation.session, generation.acting, payload.content
    )
    yield _event("user", {"message": message_public(user_message).model_dump(mode="json")})

    prompt = _prompt(generation, await _load_messages(db, generation.session.id))
    collected: list[str] = []
    try:
        async for delta in generation.client.stream(prompt):
            collected.append(delta)
            yield _event("delta", {"delta": delta})
    except ProviderError as exc:
        if collected:
            # Keep whatever arrived so the user does not lose it.
            partial = await _append_assistant_message(
                db, generation.session, "".join(collected), generation.acting.id
            )
            yield _event("message", {"message": message_public(partial).model_dump(mode="json")})
        yield _event("error", {"detail": str(exc)})
        yield _event("done", {})
        return

    assistant_message = await _append_assistant_message(
        db, generation.session, "".join(collected), generation.acting.id
    )
    yield _event("message", {"message": message_public(assistant_message).model_dump(mode="json")})
    yield _event("done", {})


def _last_assistant(messages: list[Message]) -> Message:
    target = next((message for message in reversed(messages) if message.role == "assistant"), None)
    if target is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "There is no assistant message to regenerate",
        )
    return target


async def _regenerate_context(
    db: SessionDep, session_id: int, user_id: int
) -> tuple[_Generation, list[Message], Message]:
    """The generation context, the prompt history, and the message to replace.

    The character being regenerated is the one that spoke the target message, so a
    group reply is retried in the same voice.
    """
    session = await _owned_session(db, session_id, user_id)
    messages = await _load_messages(db, session.id)
    target = _last_assistant(messages)
    generation = await _generation_context(db, session_id, user_id, target.speaker_id)
    context = [message for message in messages if message.id != target.id]
    return generation, context, target


async def _store_swipe(
    db: SessionDep, session: ChatSession, message: Message, content: str
) -> Message:
    record_swipe(message, content)
    db.add(message)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(message)
    return message


@router.post("/{session_id}/regenerate")
async def regenerate(
    session_id: int, db: SessionDep, current_user: CurrentUserDep
) -> RegenerateResult:
    generation, context, target = await _regenerate_context(db, session_id, current_user.id)
    try:
        reply = await generation.client.complete(_prompt(generation, context))
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    message = await _store_swipe(db, generation.session, target, reply)
    return RegenerateResult(assistant=message_public(message))


@router.post("/{session_id}/regenerate/stream", response_class=EventSourceResponse)
async def stream_regenerate(
    session_id: int, db: SessionDep, current_user: CurrentUserDep
) -> AsyncIterable[ServerSentEvent]:
    generation, context, target = await _regenerate_context(db, session_id, current_user.id)
    prompt = _prompt(generation, context)

    collected: list[str] = []
    try:
        async for delta in generation.client.stream(prompt):
            collected.append(delta)
            yield _event("delta", {"delta": delta})
    except ProviderError as exc:
        yield _event("error", {"detail": str(exc)})
        yield _event("done", {})
        return

    message = await _store_swipe(db, generation.session, target, "".join(collected))
    yield _event("message", {"message": message_public(message).model_dump(mode="json")})
    yield _event("done", {})


@router.get("/{session_id}/export")
async def export_session(
    session_id: int,
    db: SessionDep,
    current_user: CurrentUserDep,
    export_format: Annotated[Literal["json", "markdown"], Query(alias="format")] = "markdown",
) -> Response:
    """Download a transcript as JSON or Markdown."""
    session = await _owned_session(db, session_id, current_user.id)
    characters = await session_cast(db, session)
    primary = await readable_character(db, session.character_id, current_user.id)
    messages = await _load_messages(db, session.id)

    settings = await db.get(UserSettings, current_user.id)
    user_name = ((settings.display_name if settings else "") or "User").strip() or "User"
    primary_name = (primary.name or "").strip() or "Character"
    title = session.title or primary_name
    names = speaker_map(characters)

    if export_format == "json":
        payload = {
            "session": _summary(session).model_dump(mode="json"),
            "character": {"id": primary.id, "name": primary_name},
            "characters": [
                member.model_dump(mode="json")
                for member in cast_public(characters, session.character_id)
            ],
            "messages": [message_public(message).model_dump(mode="json") for message in messages],
        }
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers=attachment_headers(download_filename(title, "json")),
        )

    lines = [f"# {title}", ""]
    for message in messages:
        if message.role == "user":
            speaker = user_name
        elif message.role == "assistant":
            speaker = names.get(message.speaker_id or -1) or primary_name
        else:
            speaker = "System"
        lines.append(f"**{speaker}:** {message.content}")
        lines.append("")

    return Response(
        content="\n".join(lines),
        media_type="text/markdown",
        headers=attachment_headers(download_filename(title, "md")),
    )


async def _owned_message(db: SessionDep, session_id: int, message_id: int) -> Message:
    statement = select(Message).where(Message.id == message_id, Message.session_id == session_id)
    message = (await db.exec(statement)).first()
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return message


@router.patch("/{session_id}/messages/{message_id}")
async def update_message(
    session_id: int,
    message_id: int,
    payload: MessageUpdate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> MessagePublic:
    session = await _owned_session(db, session_id, current_user.id)
    message = await _owned_message(db, session.id, message_id)
    replace_active_content(message, payload.content)
    db.add(message)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(message)
    return message_public(message)


@router.delete("/{session_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    session_id: int, message_id: int, db: SessionDep, current_user: CurrentUserDep
) -> None:
    session = await _owned_session(db, session_id, current_user.id)
    message = await _owned_message(db, session.id, message_id)
    await db.delete(message)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()


@router.post("/{session_id}/messages/{message_id}/swipe")
async def swipe(
    session_id: int,
    message_id: int,
    payload: SwipeRequest,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> MessagePublic:
    session = await _owned_session(db, session_id, current_user.id)
    message = await _owned_message(db, session.id, message_id)
    if not swipe_message(message, payload.direction):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "This message has no alternative swipes",
        )
    db.add(message)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(message)
    return message_public(message)


@router.post("/{session_id}/greeting/swipe")
async def swipe_greeting(
    session_id: int,
    payload: SwipeRequest,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> MessagePublic:
    session = await _owned_session(db, session_id, current_user.id)
    messages = await _load_messages(db, session.id)
    greeting = next((message for message in messages if message.is_greeting), None)
    if greeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This session has no greeting")
    if not swipe_message(greeting, payload.direction):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "This greeting has no alternative swipes",
        )
    db.add(greeting)
    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(greeting)
    return message_public(greeting)
