"""Interactive LLM-backed character creator.

Stateless: the browser holds the conversation and the in-progress draft card,
and resends both in full each turn (see `models/character_creator.py`), so
there is nothing here to clean up if the user abandons a draft.
"""

from collections.abc import AsyncIterable

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
from sparklchat.models.character_creator import CreatorMessageRequest
from sparklchat.models.provider import Provider
from sparklchat.models.user_settings import UserSettings
from sparklchat.services.character_creator import build_messages, merge_and_validate, split_reply
from sparklchat.services.crypto import EncryptionError
from sparklchat.services.providers import (
    BaseClient,
    ProviderError,
    api_key_for,
    build_client,
    config_for,
)

router = APIRouter(prefix="/character-creator", tags=["character-creator"])

_NO_PROVIDER = "No provider configured. Add one under Settings and make it your default."


async def _resolve_provider(
    db: SessionDep, user_id: int, provider_id: int | None
) -> Provider | None:
    """The requested provider (must be the user's own), else their default."""
    if provider_id is None:
        settings = await db.get(UserSettings, user_id)
        provider_id = settings.default_provider_id if settings is not None else None
        if provider_id is None:
            return None

    provider = await db.get(Provider, provider_id)
    if provider is None or provider.user_id != user_id:
        return None
    return provider


def _client_for(provider: Provider) -> BaseClient:
    try:
        api_key = api_key_for(provider)
    except EncryptionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    try:
        return build_client(config_for(provider, api_key))
    except ProviderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _event(name: str, payload: dict) -> ServerSentEvent:
    return ServerSentEvent(data=payload, event=name)


@router.post("/message/stream", response_class=EventSourceResponse)
async def stream_creator_message(
    payload: CreatorMessageRequest,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> AsyncIterable[ServerSentEvent]:
    """Send the conversation so far and stream the assistant's next turn.

    Emits `delta` events with the raw reply text as it streams (the client
    splits its display on the draft marker as text arrives), then a final
    `message` (the reply with the patch stripped) and `draft` (the merged,
    validated card JSON) once the reply is complete.
    """
    provider = await _resolve_provider(db, current_user.id, payload.provider_id)
    if provider is None:
        yield _event("error", {"detail": _NO_PROVIDER})
        yield _event("done", {})
        return

    client = _client_for(provider)
    messages = build_messages(payload.draft, payload.messages)

    collected: list[str] = []
    try:
        async for delta in client.stream(messages):
            collected.append(delta)
            yield _event("delta", {"delta": delta})
    except ProviderError as exc:
        yield _event("error", {"detail": str(exc)})
        yield _event("done", {})
        return

    display, patch = split_reply("".join(collected))
    draft = payload.draft
    if patch is not None:
        draft, _ok = merge_and_validate(draft, patch)

    yield _event("message", {"message": display})
    yield _event("draft", {"draft": draft})
    yield _event("done", {})
