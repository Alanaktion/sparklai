"""Chat sessions, messages, streamed generation, regeneration, and swipes."""

import json
from collections.abc import AsyncIterable
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlmodel import select

from sparklchat.api.deps import CurrentUserDep
from sparklchat.config import get_settings
from sparklchat.db import SessionDep
from sparklchat.models.base import utcnow
from sparklchat.models.card import TavernCardV2
from sparklchat.models.character import Character
from sparklchat.models.chat import (
    ChatSession,
    Message,
    MessageCreate,
    MessagePair,
    MessagePublic,
    MessageUpdate,
    RegenerateResult,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    SessionUpdate,
    SwipeRequest,
)
from sparklchat.models.provider import Provider
from sparklchat.models.user_settings import UserSettings
from sparklchat.services.chat import (
    build_session_prompt,
    create_greeting,
    message_public,
    prompt_context,
    record_swipe,
    replace_active_content,
    resolve_provider,
    swipe_message,
    title_from_message,
)
from sparklchat.services.crypto import EncryptionError
from sparklchat.services.downloads import attachment_headers, download_filename
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


async def _owned_character(db: SessionDep, character_id: int, user_id: int) -> Character:
    statement = select(Character).where(Character.id == character_id, Character.user_id == user_id)
    character = (await db.exec(statement)).first()
    if character is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character


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


def _summary(session: ChatSession) -> SessionSummary:
    return SessionSummary(
        id=session.id or 0,
        character_id=session.character_id,
        title=session.title,
        provider_id=session.provider_id,
        use_character_book=session.use_character_book,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _detail(session: ChatSession, messages: list[Message]) -> SessionDetail:
    return SessionDetail(
        **_summary(session).model_dump(),
        system_prompt_override=session.system_prompt_override,
        post_history_override=session.post_history_override,
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


async def _generation_context(
    db: SessionDep, session_id: int, user_id: int
) -> tuple[ChatSession, TavernCardV2, UserSettings, Provider, BaseClient]:
    """Everything needed to build a prompt and call the provider."""
    session = await _owned_session(db, session_id, user_id)
    character = await _owned_character(db, session.character_id, user_id)
    card = TavernCardV2.model_validate(character.card_json)
    settings = await get_or_create_settings(db, user_id)

    provider = await resolve_provider(db, session, user_id)
    if provider is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _NO_PROVIDER)

    return session, card, settings, provider, _client_for(provider)


def _prompt(
    card: TavernCardV2,
    session: ChatSession,
    settings: UserSettings,
    messages: list[Message],
):
    settings_values = get_settings()
    return build_session_prompt(
        card=card,
        session=session,
        messages=messages,
        settings=settings,
        context_window=settings_values.context_window,
        context_reserve=settings_values.context_reserve,
    )


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


async def _append_assistant_message(db: SessionDep, session: ChatSession, content: str) -> Message:
    message = Message(
        session_id=session.id,
        role="assistant",
        content=content,
        token_count=count_tokens(content),
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
    await _owned_character(db, character_id, current_user.id)
    statement = (
        select(ChatSession)
        .where(
            ChatSession.user_id == current_user.id,
            ChatSession.character_id == character_id,
        )
        .order_by(ChatSession.updated_at.desc())
    )
    return [_summary(row) for row in (await db.exec(statement)).all()]


@character_router.post("/{character_id}/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    character_id: int,
    payload: SessionCreate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> SessionDetail:
    """Start a session and seed it with the character's greeting."""
    character = await _owned_character(db, character_id, current_user.id)
    if payload.provider_id is not None:
        await _owned_provider(db, payload.provider_id, current_user.id)

    card = TavernCardV2.model_validate(character.card_json)
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

    greeting = await create_greeting(db, session, card, prompt_context(card, settings))
    messages = [greeting] if greeting is not None else []
    return _detail(session, messages)


@router.get("/{session_id}")
async def get_session(
    session_id: int, db: SessionDep, current_user: CurrentUserDep
) -> SessionDetail:
    session = await _owned_session(db, session_id, current_user.id)
    return _detail(session, await _load_messages(db, session.id))


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

    session.updated_at = utcnow()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _detail(session, await _load_messages(db, session.id))


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
    session, card, settings, _, client = await _generation_context(db, session_id, current_user.id)
    character = await _owned_character(db, session.character_id, current_user.id)
    user_message = await _append_user_message(db, session, character, payload.content)

    prompt = _prompt(card, session, settings, await _load_messages(db, session.id))
    try:
        reply = await client.complete(prompt)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    assistant_message = await _append_assistant_message(db, session, reply)
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
    session, card, settings, _, client = await _generation_context(db, session_id, current_user.id)
    character = await _owned_character(db, session.character_id, current_user.id)
    user_message = await _append_user_message(db, session, character, payload.content)
    yield _event("user", {"message": message_public(user_message).model_dump(mode="json")})

    prompt = _prompt(card, session, settings, await _load_messages(db, session.id))
    collected: list[str] = []
    try:
        async for delta in client.stream(prompt):
            collected.append(delta)
            yield _event("delta", {"delta": delta})
    except ProviderError as exc:
        if collected:
            # Keep whatever arrived so the user does not lose it.
            partial = await _append_assistant_message(db, session, "".join(collected))
            yield _event("message", {"message": message_public(partial).model_dump(mode="json")})
        yield _event("error", {"detail": str(exc)})
        yield _event("done", {})
        return

    assistant_message = await _append_assistant_message(db, session, "".join(collected))
    yield _event("message", {"message": message_public(assistant_message).model_dump(mode="json")})
    yield _event("done", {})


async def _regenerate_prompt(
    db: SessionDep, session: ChatSession, card: TavernCardV2, settings: UserSettings
) -> tuple[list[Message], Message]:
    """Return the prompt messages and the assistant message being replaced."""
    messages = await _load_messages(db, session.id)
    target = next((message for message in reversed(messages) if message.role == "assistant"), None)
    if target is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "There is no assistant message to regenerate",
        )
    context = [message for message in messages if message.id != target.id]
    return _prompt(card, session, settings, context), target


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
    session, card, settings, _, client = await _generation_context(db, session_id, current_user.id)
    prompt, target = await _regenerate_prompt(db, session, card, settings)
    try:
        reply = await client.complete(prompt)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    message = await _store_swipe(db, session, target, reply)
    return RegenerateResult(assistant=message_public(message))


@router.post("/{session_id}/regenerate/stream", response_class=EventSourceResponse)
async def stream_regenerate(
    session_id: int, db: SessionDep, current_user: CurrentUserDep
) -> AsyncIterable[ServerSentEvent]:
    session, card, settings, _, client = await _generation_context(db, session_id, current_user.id)
    prompt, target = await _regenerate_prompt(db, session, card, settings)

    collected: list[str] = []
    try:
        async for delta in client.stream(prompt):
            collected.append(delta)
            yield _event("delta", {"delta": delta})
    except ProviderError as exc:
        yield _event("error", {"detail": str(exc)})
        yield _event("done", {})
        return

    message = await _store_swipe(db, session, target, "".join(collected))
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
    character = await _owned_character(db, session.character_id, current_user.id)
    messages = await _load_messages(db, session.id)

    settings = await db.get(UserSettings, current_user.id)
    user_name = ((settings.display_name if settings else "") or "User").strip() or "User"
    character_name = (character.name or "").strip() or "Character"
    title = session.title or character_name

    if export_format == "json":
        payload = {
            "session": _summary(session).model_dump(mode="json"),
            "character": {"id": character.id, "name": character_name},
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
            speaker = character_name
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
