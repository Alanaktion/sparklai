"""Group chats: a session whose cast holds more than one character (M8)."""

import copy
from collections.abc import AsyncIterator

from httpx import AsyncClient

from sparklchat.services.providers import ChatMessage


class StubClient:
    def __init__(self, reply: str = "ok") -> None:
        self.prompts: list[list[ChatMessage]] = []
        self._reply = reply

    async def complete(self, messages) -> str:
        self.prompts.append(list(messages))
        return self._reply

    async def stream(self, messages) -> AsyncIterator[str]:
        self.prompts.append(list(messages))
        yield self._reply


def install_stub(monkeypatch, **kwargs) -> StubClient:
    stub = StubClient(**kwargs)
    monkeypatch.setattr("sparklchat.api.chat.build_client", lambda config: stub)
    return stub


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
        "/api/settings", json={"default_provider_id": provider["id"]}, headers=headers
    )
    return provider


async def make_character(
    client: AsyncClient, headers: dict[str, str], card: dict, name: str | None = None
) -> dict:
    payload = copy.deepcopy(card)
    if name is not None:
        payload["data"]["name"] = name
    response = await client.post("/api/characters", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def make_session(
    client: AsyncClient, headers: dict[str, str], character_id: int, **body
) -> dict:
    response = await client.post(
        f"/api/characters/{character_id}/sessions", json=body, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def card(name: str, **data) -> dict:
    payload = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": name,
            "description": f"{name} is here.",
            "first_mes": f"Hi, I am {name}.",
            "mes_example": "",
            "extensions": {},
        },
    }
    payload["data"].update(data)
    return payload


async def test_a_session_starts_with_a_single_character_cast(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    character = await make_character(client, auth_headers, card("Haruhi"))
    session = await make_session(client, auth_headers, character["id"])

    assert [member["name"] for member in session["characters"]] == ["Haruhi"]
    assert session["characters"][0]["is_primary"] is True
    assert session["characters"][0]["id"] == character["id"]
    assert session["messages"][0]["speaker_id"] == character["id"]


async def test_creating_a_group_lists_the_cast_primary_first(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    yuki = await make_character(client, auth_headers, card("Yuki"))

    session = await make_session(
        client,
        auth_headers,
        haruhi["id"],
        character_ids=[mikuru["id"], yuki["id"]],
    )

    assert [member["name"] for member in session["characters"]] == [
        "Haruhi",
        "Mikuru",
        "Yuki",
    ]
    assert [member["is_primary"] for member in session["characters"]] == [
        True,
        False,
        False,
    ]

    fetched = await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    assert [member["name"] for member in fetched.json()["characters"]] == [
        "Haruhi",
        "Mikuru",
        "Yuki",
    ]


async def test_duplicate_and_primary_members_are_ignored(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))

    session = await make_session(
        client,
        auth_headers,
        haruhi["id"],
        character_ids=[haruhi["id"], mikuru["id"], mikuru["id"]],
    )
    assert [member["name"] for member in session["characters"]] == ["Haruhi", "Mikuru"]


async def test_group_members_must_be_readable(
    client: AsyncClient, auth_headers: dict[str, str], login_as
) -> None:
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    private = await make_character(client, auth_headers, card("Secret"))
    other = await login_as("misty@example.com")

    # Someone else's private character cannot be pulled into your group.
    response = await client.post(
        f"/api/characters/{haruhi['id']}/sessions",
        json={"character_ids": [private["id"]]},
        headers=other,
    )
    assert response.status_code == 404

    # Nor can a character that does not exist.
    response = await client.post(
        f"/api/characters/{haruhi['id']}/sessions",
        json={"character_ids": [9999]},
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_a_public_character_can_join_a_group(
    client: AsyncClient, auth_headers: dict[str, str], login_as
) -> None:
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    shared = await make_character(client, auth_headers, card("Shared"))
    await client.patch(
        f"/api/characters/{shared['id']}", json={"is_public": True}, headers=auth_headers
    )

    other = await login_as("misty@example.com")
    mine = await make_character(client, other, card("Mine"))
    session = await make_session(client, other, mine["id"], character_ids=[shared["id"]])
    assert [member["name"] for member in session["characters"]] == ["Mine", "Shared"]

    # The unpublished one stays out of reach.
    blocked = await client.post(
        f"/api/characters/{mine['id']}/sessions",
        json={"character_ids": [haruhi["id"]]},
        headers=other,
    )
    assert blocked.status_code == 404


async def test_speaker_selects_who_replies(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])

    stub = install_stub(monkeypatch, reply="as Mikuru")
    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hello", "speaker_id": mikuru["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["assistant"]["speaker_id"] == mikuru["id"]

    system = stub.prompts[-1][0].content
    assert "Mikuru is here." in system
    assert "Haruhi is here." in system
    # The acting character is the one the directive names.
    assert "Mikuru's next" in system


async def test_the_default_speaker_is_the_primary(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])

    install_stub(monkeypatch, reply="as Haruhi")
    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hello"},
        headers=auth_headers,
    )
    assert response.json()["assistant"]["speaker_id"] == haruhi["id"]


async def test_an_unknown_speaker_is_rejected(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    outsider = await make_character(client, auth_headers, card("Outsider"))
    session = await make_session(client, auth_headers, haruhi["id"])
    install_stub(monkeypatch, reply="ok")

    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi", "speaker_id": outsider["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "speaker_id" in response.json()["detail"]


async def test_previous_group_turns_are_labelled_with_their_speaker(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])

    stub = install_stub(monkeypatch, reply="Haruhi speaks")
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi", "speaker_id": haruhi["id"]},
        headers=auth_headers,
    )

    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "your turn", "speaker_id": mikuru["id"]},
        headers=auth_headers,
    )
    history = [message.content for message in stub.prompts[-1][1:]]
    assert "Haruhi: Haruhi speaks" in history


async def test_regenerating_keeps_the_speaker(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])
    install_stub(monkeypatch, reply="first")

    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi", "speaker_id": mikuru["id"]},
        headers=auth_headers,
    )

    stub = install_stub(monkeypatch, reply="second")
    response = await client.post(f"/api/sessions/{session['id']}/regenerate", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["assistant"]["speaker_id"] == mikuru["id"]
    # The retry is written as Mikuru again.
    assert "Mikuru's next" in stub.prompts[-1][0].content


async def test_cast_lorebooks_are_stacked(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    book = {
        "extensions": {},
        "entries": [{"keys": ["trombone"], "content": "MARKER-LORE", "extensions": {}}],
    }
    mikuru = await make_character(client, auth_headers, card("Mikuru", character_book=book))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])

    stub = install_stub(monkeypatch, reply="ok")
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "the trombone", "speaker_id": haruhi["id"]},
        headers=auth_headers,
    )
    assert "MARKER-LORE" in stub.prompts[-1][0].content


async def test_deleting_a_member_shrinks_the_cast(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])

    assert (
        await client.delete(f"/api/characters/{mikuru['id']}", headers=auth_headers)
    ).status_code == 204

    detail = await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert [member["name"] for member in detail.json()["characters"]] == ["Haruhi"]


async def test_deleting_the_primary_removes_the_session(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])

    await client.delete(f"/api/characters/{haruhi['id']}", headers=auth_headers)
    assert (
        await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    ).status_code == 404


async def test_export_names_every_group_speaker(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    haruhi = await make_character(client, auth_headers, card("Haruhi"))
    mikuru = await make_character(client, auth_headers, card("Mikuru"))
    session = await make_session(client, auth_headers, haruhi["id"], character_ids=[mikuru["id"]])
    install_stub(monkeypatch, reply="Mikuru says hi")
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hello", "speaker_id": mikuru["id"]},
        headers=auth_headers,
    )

    response = await client.get(f"/api/sessions/{session['id']}/export", headers=auth_headers)
    assert "**Mikuru:** Mikuru says hi" in response.text

    payload = await client.get(
        f"/api/sessions/{session['id']}/export",
        params={"format": "json"},
        headers=auth_headers,
    )
    names = [member["name"] for member in payload.json()["characters"]]
    assert names == ["Haruhi", "Mikuru"]
