"""Provider CRUD, key encryption, default wiring, and the test/complete endpoints."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.provider import Provider
from sparklchat.services.providers import (
    BaseClient,
    ChatMessage,
    ProviderConfig,
    ProviderError,
)


class StubClient(BaseClient):
    """Stands in for a real client so the endpoints can be tested offline."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        reply: str = "",
        error: str | None = None,
        chunks: Sequence[str] = (),
    ) -> None:
        super().__init__(config)
        self._reply = reply
        self._error = error
        self._chunks = chunks

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        if self._error:
            raise ProviderError(self._error)
        return self._reply

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        if self._error:
            raise ProviderError(self._error)
        for chunk in self._chunks:
            yield chunk


def provider_body(**overrides: Any) -> dict:
    body: dict[str, Any] = {
        "name": "Local Ollama",
        "provider_type": "ollama",
        "model": "llama3",
        "base_url": "http://127.0.0.1:11434",
        "api_key": "sk-test-secret",
        "temperature": 0.8,
        "max_tokens": 256,
        "top_p": 0.9,
        "extra_params": {"keep_alive": "5m"},
    }
    body.update(overrides)
    return body


async def create(client: AsyncClient, headers: dict[str, str], **overrides: Any) -> dict:
    response = await client.post("/api/providers", json=provider_body(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/providers")).status_code == 401
    assert (await client.post("/api/providers", json=provider_body())).status_code == 401


async def test_create_returns_public_view_without_the_key(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    body = await create(client, auth_headers)

    assert body["name"] == "Local Ollama"
    assert body["provider_type"] == "ollama"
    assert body["model"] == "llama3"
    assert body["has_api_key"] is True
    assert body["is_default"] is False
    assert "api_key" not in body
    assert "api_key_encrypted" not in body


async def test_api_key_is_encrypted_at_rest(
    client: AsyncClient, auth_headers: dict[str, str], engine: AsyncEngine
) -> None:
    created = await create(client, auth_headers)

    async with AsyncSession(engine) as session:
        row = (await session.exec(select(Provider).where(Provider.id == created["id"]))).one()

    assert row.api_key_encrypted
    assert row.api_key_encrypted != "sk-test-secret"
    assert "sk-test-secret" not in row.api_key_encrypted


async def test_default_base_url_is_applied(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(
        client, auth_headers, name="OpenAI", provider_type="openai", base_url=None
    )
    assert created["base_url"] == "https://api.openai.com/v1"


async def test_custom_provider_requires_a_base_url(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/providers",
        json=provider_body(provider_type="custom", base_url=None),
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_invalid_sampling_values_are_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/providers", json=provider_body(temperature=5), headers=auth_headers
    )
    assert response.status_code == 422


async def test_model_is_required(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/providers", json=provider_body(model=""), headers=auth_headers
    )
    assert response.status_code == 422


async def test_list_and_get(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await create(client, auth_headers)

    listing = await client.get("/api/providers", headers=auth_headers)
    assert [item["id"] for item in listing.json()] == [created["id"]]

    fetched = await client.get(f"/api/providers/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["model"] == "llama3"


async def test_patch_only_touches_provided_fields(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(client, auth_headers)
    provider_id = created["id"]

    renamed = await client.patch(
        f"/api/providers/{provider_id}", json={"name": "Renamed"}, headers=auth_headers
    )
    assert renamed.json()["name"] == "Renamed"
    # Omitted fields are left alone, including the stored key.
    assert renamed.json()["has_api_key"] is True
    assert renamed.json()["model"] == "llama3"

    cleared = await client.patch(
        f"/api/providers/{provider_id}", json={"api_key": None}, headers=auth_headers
    )
    assert cleared.json()["has_api_key"] is False


async def test_changing_type_resets_the_endpoint(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(client, auth_headers)
    updated = await client.patch(
        f"/api/providers/{created['id']}",
        json={"provider_type": "anthropic"},
        headers=auth_headers,
    )
    assert updated.json()["base_url"] == "https://api.anthropic.com"


async def test_providers_are_isolated_per_user(
    client: AsyncClient, auth_headers: dict[str, str], login_as
) -> None:
    created = await create(client, auth_headers)
    other = await login_as("misty@example.com")

    assert (await client.get("/api/providers", headers=other)).json() == []
    assert (await client.get(f"/api/providers/{created['id']}", headers=other)).status_code == 404
    assert (
        await client.patch(f"/api/providers/{created['id']}", json={"name": "Nope"}, headers=other)
    ).status_code == 404


async def test_setting_a_default_provider(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(client, auth_headers)

    await client.patch(
        "/api/settings",
        json={"default_provider_id": created["id"]},
        headers=auth_headers,
    )
    fetched = await client.get(f"/api/providers/{created['id']}", headers=auth_headers)
    assert fetched.json()["is_default"] is True

    listing = await client.get("/api/providers", headers=auth_headers)
    assert [item["is_default"] for item in listing.json()] == [True]


async def test_default_provider_must_be_owned_by_the_user(
    client: AsyncClient, auth_headers: dict[str, str], login_as
) -> None:
    other = await login_as("misty@example.com")
    theirs = await create(client, other, name="Theirs")

    response = await client.patch(
        "/api/settings",
        json={"default_provider_id": theirs["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_delete_clears_the_default_reference(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(client, auth_headers)
    provider_id = created["id"]
    await client.patch(
        "/api/settings",
        json={"default_provider_id": provider_id},
        headers=auth_headers,
    )

    assert (
        await client.delete(f"/api/providers/{provider_id}", headers=auth_headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/providers/{provider_id}", headers=auth_headers)
    ).status_code == 404

    settings = await client.get("/api/settings", headers=auth_headers)
    assert settings.json()["default_provider_id"] is None


async def test_connection_test_reports_success(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    created = await create(client, auth_headers)
    monkeypatch.setattr(
        "sparklchat.api.providers.build_client",
        lambda config: StubClient(config, reply="ok"),
    )

    response = await client.post(f"/api/providers/{created['id']}/test", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reply"] == "ok"


async def test_connection_test_reports_failure(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    created = await create(client, auth_headers)
    monkeypatch.setattr(
        "sparklchat.api.providers.build_client",
        lambda config: StubClient(config, error="invalid api key"),
    )

    body = (await client.post(f"/api/providers/{created['id']}/test", headers=auth_headers)).json()
    assert body["ok"] is False
    assert "invalid api key" in body["message"]


async def test_complete_returns_the_reply(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    created = await create(client, auth_headers)
    monkeypatch.setattr(
        "sparklchat.api.providers.build_client",
        lambda config: StubClient(config, reply="hello there"),
    )

    response = await client.post(
        f"/api/providers/{created['id']}/complete",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "hello there"}


async def test_complete_maps_provider_errors_to_502(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    created = await create(client, auth_headers)
    monkeypatch.setattr(
        "sparklchat.api.providers.build_client",
        lambda config: StubClient(config, error="upstream exploded"),
    )

    response = await client.post(
        f"/api/providers/{created['id']}/complete",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert "upstream exploded" in response.json()["detail"]


async def test_complete_requires_at_least_one_message(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await create(client, auth_headers)
    response = await client.post(
        f"/api/providers/{created['id']}/complete",
        json={"messages": []},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_streaming_completion_emits_server_sent_events(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    created = await create(client, auth_headers)
    monkeypatch.setattr(
        "sparklchat.api.providers.build_client",
        lambda config: StubClient(config, chunks=["Hel", "lo"]),
    )

    async with client.stream(
        "POST",
        f"/api/providers/{created['id']}/complete/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: delta" in payload
    assert '"Hel"' in payload
    assert '"lo"' in payload
    assert "event: done" in payload


async def test_streaming_completion_reports_errors_as_events(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    created = await create(client, auth_headers)
    monkeypatch.setattr(
        "sparklchat.api.providers.build_client",
        lambda config: StubClient(config, error="stream blew up"),
    )

    async with client.stream(
        "POST",
        f"/api/providers/{created['id']}/complete/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "stream blew up" in payload
