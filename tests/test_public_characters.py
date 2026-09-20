"""Publishing characters and the access rules around them."""

import copy
from collections.abc import AsyncIterator

from httpx import AsyncClient

from sparklchat.services.png import blank_png, embed_card_json
from sparklchat.services.providers import ChatMessage


class StubClient:
    def __init__(self, reply: str) -> None:
        self.prompts: list[list[ChatMessage]] = []
        self._reply = reply

    async def complete(self, messages) -> str:
        self.prompts.append(list(messages))
        return self._reply

    async def stream(self, messages) -> AsyncIterator[str]:
        self.prompts.append(list(messages))
        yield self._reply


async def make_character(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def make_provider(client: AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/providers",
        json={
            "name": "Test provider",
            "provider_type": "openai",
            "base_url": "https://api.example/v1",
            "api_key": "sk-test",
            "model": "test-model",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    provider = response.json()
    await client.patch(
        "/api/settings",
        json={"default_provider_id": provider["id"]},
        headers=headers,
    )
    return provider


async def publish(client: AsyncClient, headers: dict[str, str], character_id: int) -> dict:
    response = await client.patch(
        f"/api/characters/{character_id}",
        json={"is_public": True},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_new_characters_start_private(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    assert created["is_public"] is False
    assert created["is_mine"] is True


async def test_publishing_needs_no_card(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    body = await publish(client, auth_headers, created["id"])
    # The card is untouched by the flag flip.
    assert body["is_public"] is True
    assert body["card"] == created["card"]

    again = await client.get(f"/api/characters/{created['id']}", headers=auth_headers)
    assert again.json()["is_public"] is True


async def test_empty_patch_is_still_rejected(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    response = await client.patch(f"/api/characters/{created['id']}", json={}, headers=auth_headers)
    assert response.status_code == 422


async def test_public_scope_lists_other_users_characters(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    shared = await make_character(client, auth_headers, v2_card)
    await publish(client, auth_headers, shared["id"])

    private_card = copy.deepcopy(v2_card)
    private_card["data"]["name"] = "Secret"
    await make_character(client, auth_headers, private_card)

    other = await login_as("misty@example.com")

    # The other user owns nothing, so `mine` is empty…
    mine = await client.get("/api/characters", headers=other)
    assert mine.json() == []

    # …but the published character shows up, flagged as not theirs.
    public = await client.get("/api/characters", params={"scope": "public"}, headers=other)
    names = [c["name"] for c in public.json()]
    assert names == ["Haruhi"]
    assert public.json()[0]["is_mine"] is False
    assert public.json()[0]["is_public"] is True


async def test_private_character_is_invisible_to_others(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    other = await login_as("misty@example.com")

    assert (await client.get(f"/api/characters/{created['id']}", headers=other)).status_code == 404
    assert (
        await client.get(f"/api/characters/{created['id']}/export", headers=other)
    ).status_code == 404
    assert (
        await client.get(f"/api/characters/{created['id']}/avatar", headers=other)
    ).status_code == 404
    assert (
        await client.post(f"/api/characters/{created['id']}/sessions", json={}, headers=other)
    ).status_code == 404


async def test_only_the_owner_can_patch_or_delete(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    await publish(client, auth_headers, created["id"])
    other = await login_as("misty@example.com")

    # Reading a public character does not grant editing rights.
    assert (await client.get(f"/api/characters/{created['id']}", headers=other)).status_code == 200

    patch = await client.patch(
        f"/api/characters/{created['id']}", json={"is_public": False}, headers=other
    )
    assert patch.status_code == 404
    assert (
        await client.delete(f"/api/characters/{created['id']}", headers=other)
    ).status_code == 404

    # The owner's view is unchanged by the failed attempts.
    assert (await client.get(f"/api/characters/{created['id']}", headers=auth_headers)).json()[
        "is_public"
    ] is True


async def test_non_owner_can_read_and_export_a_public_character(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    png = embed_card_json(blank_png(), v2_card)
    uploaded = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.png", png, "image/png")},
        headers=auth_headers,
    )
    created = uploaded.json()[0]["character"]
    await publish(client, auth_headers, created["id"])
    other = await login_as("misty@example.com")

    detail = await client.get(f"/api/characters/{created['id']}", headers=other)
    assert detail.status_code == 200
    assert detail.json()["is_mine"] is False

    exported = await client.get(f"/api/characters/{created['id']}/export", headers=other)
    assert exported.status_code == 200
    assert exported.json()["data"]["name"] == "Haruhi"

    avatar = await client.get(f"/api/characters/{created['id']}/avatar", headers=other)
    assert avatar.status_code == 200
    assert avatar.headers["content-type"] == "image/webp"


async def test_non_owner_can_chat_with_a_public_character(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict, monkeypatch
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    await publish(client, auth_headers, created["id"])

    stub = StubClient("Sure!")
    monkeypatch.setattr("sparklchat.api.chat.build_client", lambda config: stub)

    other = await login_as("misty@example.com")
    await make_provider(client, other)

    session = await client.post(f"/api/characters/{created['id']}/sessions", json={}, headers=other)
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]

    sent = await client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "hello"}, headers=other
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["assistant"]["content"] == "Sure!"

    # The other user can list their own sessions on someone else's public card.
    listed = await client.get(f"/api/characters/{created['id']}/sessions", headers=other)
    assert [row["id"] for row in listed.json()] == [session_id]


async def test_unpublishing_hides_the_character_again(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    created = await make_character(client, auth_headers, v2_card)
    await publish(client, auth_headers, created["id"])
    other = await login_as("misty@example.com")

    assert (await client.get(f"/api/characters/{created['id']}", headers=other)).status_code == 200

    response = await client.patch(
        f"/api/characters/{created['id']}", json={"is_public": False}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["is_public"] is False

    assert (await client.get(f"/api/characters/{created['id']}", headers=other)).status_code == 404
