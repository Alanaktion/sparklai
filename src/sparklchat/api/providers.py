"""Provider CRUD, connection testing, and one-off completions."""

from collections.abc import AsyncIterable
from dataclasses import replace

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlmodel import select

from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
from sparklchat.models.base import utcnow
from sparklchat.models.provider import (
    CompletionRequest,
    CompletionResult,
    Provider,
    ProviderCreate,
    ProviderPublic,
    ProviderTestResult,
    ProviderUpdate,
    default_base_url,
)
from sparklchat.models.user_settings import UserSettings
from sparklchat.services.crypto import EncryptionError, decrypt, encrypt
from sparklchat.services.providers import (
    BaseClient,
    ChatMessage,
    ProviderError,
    build_client,
    config_for,
)

router = APIRouter(prefix="/providers", tags=["providers"])

TEST_PROMPT = "Reply with the single word: ok"
# Keep connection tests cheap regardless of the provider's configured limit, but
# leave enough headroom that reasoning models still emit visible content.
TEST_MAX_TOKENS = 64


async def _owned(db: SessionDep, provider_id: int, user_id: int) -> Provider:
    statement = select(Provider).where(Provider.id == provider_id, Provider.user_id == user_id)
    provider = (await db.exec(statement)).first()
    if provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    return provider


async def _default_provider_id(db: SessionDep, user_id: int) -> int | None:
    settings = await db.get(UserSettings, user_id)
    return settings.default_provider_id if settings is not None else None


def _public(provider: Provider, default_id: int | None) -> ProviderPublic:
    return ProviderPublic(
        id=provider.id or 0,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        top_p=provider.top_p,
        extra_params=provider.extra_params or {},
        has_api_key=bool(provider.api_key_encrypted),
        is_default=provider.id is not None and provider.id == default_id,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _stored_key(provider: Provider) -> str | None:
    if not provider.api_key_encrypted:
        return None
    try:
        return decrypt(provider.api_key_encrypted)
    except EncryptionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc


def _client_for(provider: Provider, *, max_tokens: int | None = None) -> BaseClient:
    config = config_for(provider, _stored_key(provider))
    if max_tokens is not None:
        config = replace(config, max_tokens=max_tokens)
    try:
        return build_client(config)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _messages(payload: CompletionRequest) -> list[ChatMessage]:
    return [ChatMessage(role=item.role, content=item.content) for item in payload.messages]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate, db: SessionDep, current_user: CurrentUserDep
) -> ProviderPublic:
    base_url = (payload.base_url or "").strip() or default_base_url(payload.provider_type)
    if not base_url:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "base_url is required for custom providers",
        )

    provider = Provider(
        user_id=current_user.id,
        name=payload.name,
        provider_type=payload.provider_type,
        base_url=base_url,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        top_p=payload.top_p,
        extra_params=payload.extra_params,
        api_key_encrypted=encrypt(payload.api_key) if payload.api_key else None,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return _public(provider, await _default_provider_id(db, current_user.id))


@router.get("")
async def list_providers(db: SessionDep, current_user: CurrentUserDep) -> list[ProviderPublic]:
    default_id = await _default_provider_id(db, current_user.id)
    statement = select(Provider).where(Provider.user_id == current_user.id).order_by(Provider.name)
    return [_public(row, default_id) for row in (await db.exec(statement)).all()]


@router.get("/{provider_id}")
async def get_provider(
    provider_id: int, db: SessionDep, current_user: CurrentUserDep
) -> ProviderPublic:
    provider = await _owned(db, provider_id, current_user.id)
    return _public(provider, await _default_provider_id(db, current_user.id))


@router.patch("/{provider_id}")
async def update_provider(
    provider_id: int,
    payload: ProviderUpdate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> ProviderPublic:
    provider = await _owned(db, provider_id, current_user.id)
    data = payload.model_dump(exclude_unset=True)
    previous_type = provider.provider_type

    if data.get("name") is not None:
        provider.name = data["name"]
    if data.get("provider_type") is not None:
        provider.provider_type = data["provider_type"]
    if data.get("model") is not None:
        provider.model = data["model"]
    if "temperature" in data:
        provider.temperature = data["temperature"]
    if "max_tokens" in data:
        provider.max_tokens = data["max_tokens"]
    if "top_p" in data:
        provider.top_p = data["top_p"]
    if data.get("extra_params") is not None:
        provider.extra_params = data["extra_params"]
    if "api_key" in data:
        api_key = data["api_key"]
        provider.api_key_encrypted = encrypt(api_key) if api_key else None

    supplied_base_url = (data.get("base_url") or "").strip()
    if supplied_base_url:
        provider.base_url = supplied_base_url
    elif provider.provider_type != previous_type or not provider.base_url.strip():
        # Switching type should not silently keep the old endpoint.
        provider.base_url = default_base_url(provider.provider_type)

    if not provider.base_url:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "base_url is required for custom providers",
        )

    provider.updated_at = utcnow()
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return _public(provider, await _default_provider_id(db, current_user.id))


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: int, db: SessionDep, current_user: CurrentUserDep) -> None:
    provider = await _owned(db, provider_id, current_user.id)

    # Keep the user's default pointing at a provider that still exists.
    settings = await db.get(UserSettings, current_user.id)
    if settings is not None and settings.default_provider_id == provider_id:
        settings.default_provider_id = None
        db.add(settings)

    await db.delete(provider)
    await db.commit()


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: int, db: SessionDep, current_user: CurrentUserDep
) -> ProviderTestResult:
    """Send a tiny prompt so the user can verify credentials and reachability."""
    provider = await _owned(db, provider_id, current_user.id)
    client = _client_for(provider, max_tokens=TEST_MAX_TOKENS)
    try:
        reply = await client.complete([ChatMessage(role="user", content=TEST_PROMPT)])
    except ProviderError as exc:
        return ProviderTestResult(ok=False, message=str(exc))
    return ProviderTestResult(ok=True, message="Connection succeeded", reply=reply.strip()[:500])


@router.post("/{provider_id}/complete")
async def complete_provider(
    provider_id: int,
    payload: CompletionRequest,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CompletionResult:
    """One-off completion, handy for debugging a provider before chat exists."""
    provider = await _owned(db, provider_id, current_user.id)
    client = _client_for(provider)
    try:
        reply = await client.complete(_messages(payload))
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return CompletionResult(reply=reply)


@router.post("/{provider_id}/complete/stream", response_class=EventSourceResponse)
async def stream_provider_completion(
    provider_id: int,
    payload: CompletionRequest,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> AsyncIterable[ServerSentEvent]:
    """Same as `complete`, but streamed as Server-Sent Events."""
    provider = await _owned(db, provider_id, current_user.id)
    client = _client_for(provider)
    messages = _messages(payload)

    try:
        async for delta in client.stream(messages):
            yield ServerSentEvent(data={"delta": delta}, event="delta")
    except ProviderError as exc:
        yield ServerSentEvent(data={"detail": str(exc)}, event="error")
    yield ServerSentEvent(data={}, event="done")
