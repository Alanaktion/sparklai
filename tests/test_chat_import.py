"""Importing chat transcripts from JSON.

Two families are covered: this app's own export, and the message-list JSON other
clients write (a `msg`/`handle` body with `characterId`/`userId` speakers).
"""

import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.chat import Message
from sparklchat.services.chat_import import ChatImportError, parse_chat

TITLE = "Otori mansion"


async def make_character(
    client: AsyncClient, headers: dict[str, str], card: dict, name: str | None = None
) -> dict:
    payload = card
    if name is not None:
        payload = {**card, "data": {**card["data"], "name": name}}
    response = await client.post("/api/characters", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def import_chat(
    client: AsyncClient, headers: dict[str, str], character_id: int, payload: object
) -> object:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return await client.post(
        f"/api/characters/{character_id}/sessions/import",
        files={"file": ("chat.json", body, "application/json")},
        headers=headers,
    )


async def seed_transcript(
    client: AsyncClient, engine: AsyncEngine, headers: dict[str, str], v2_card: dict
) -> tuple[dict, dict]:
    """A character, a titled session, and one exchange, for export round trips."""
    character = await make_character(client, headers, v2_card)
    created = await client.post(
        f"/api/characters/{character['id']}/sessions", json={}, headers=headers
    )
    assert created.status_code == 201, created.text
    session = created.json()

    renamed = await client.patch(
        f"/api/sessions/{session['id']}", json={"title": TITLE}, headers=headers
    )
    assert renamed.status_code == 200, renamed.text

    async with AsyncSession(engine) as db:
        db.add(Message(session_id=session["id"], role="user", content="Who are you?"))
        db.add(Message(session_id=session["id"], role="assistant", content="Fine, whatever."))
        await db.commit()
    return character, session


def message_list_payload() -> dict:
    """The message-list shape: `msg` bodies, `characterId`/`userId` speakers."""
    return {
        "name": TITLE,
        "greeting": "WONDERHOY!!!!!! Its so nice to see you again!!!!",
        "sampleChat": "",
        "scenario": "",
        "treeLeafId": "390578dc-4268-499b-bd04-e1350ce93d21",
        "messages": [
            {
                "_id": "e09e7029",
                "createdAt": "2026-08-30T16:23:33.618Z",
                "handle": "Emu",
                "characterId": "imported",
                "name": "Emu",
                "msg": "WONDERHOY!!!!!! Its so nice to see you again!!!!",
            },
            {
                "_id": "0bc2c362",
                "createdAt": "2026-08-30T16:26:30.201Z",
                "ooc": False,
                "parent": "e09e7029",
                "handle": "Alan",
                "userId": "476e0f7a-d51d-4af1-bb18-f4a266ab3654",
                "name": "Alan",
                "msg": "Emu!!!! I missed you cutie!",
            },
            {
                "_id": "70f48211",
                "createdAt": "2026-08-30T16:34:07.042Z",
                "ooc": False,
                "parent": "0bc2c362",
                "handle": "Emu",
                "characterId": "imported",
                "name": "Emu",
                "msg": "Yaaahhh!! I missed you too, Alan-kun!",
            },
        ],
    }


def export_payload() -> dict:
    """The shape `GET /api/sessions/{id}/export?format=json` returns."""
    return {
        "session": {"id": 99, "character_id": 1, "title": "The Brigade"},
        "character": {"id": 1, "name": "Haruhi"},
        "characters": [
            {"id": 1, "name": "Haruhi", "has_avatar": False, "is_primary": True},
            {"id": 2, "name": "Mikuru", "has_avatar": False, "is_primary": False},
        ],
        "messages": [
            {
                "id": 1,
                "session_id": 99,
                "role": "assistant",
                "content": "Hi!",
                "created_at": "2026-08-01T10:00:00+00:00",
                "is_greeting": True,
                "swipe_index": 0,
                "swipe_count": 1,
                "speaker_id": 1,
            },
            {
                "id": 2,
                "session_id": 99,
                "role": "user",
                "content": "Who are you?",
                "created_at": "2026-08-01T10:00:05+00:00",
                "is_greeting": False,
                "swipe_index": 0,
                "swipe_count": 1,
                "speaker_id": None,
            },
            {
                "id": 3,
                "session_id": 99,
                "role": "assistant",
                "content": "Mikuru here.",
                "created_at": "2026-08-01T10:00:10+00:00",
                "is_greeting": False,
                "swipe_index": 0,
                "swipe_count": 1,
                "speaker_id": 2,
            },
        ],
    }


async def test_import_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/characters/1/sessions/import",
        files={"file": ("chat.json", b"{}", "application/json")},
    )
    assert response.status_code == 401


async def test_import_round_trips_this_apps_export(
    client: AsyncClient,
    auth_headers: dict[str, str],
    engine: AsyncEngine,
    v2_card: dict,
) -> None:
    character, session = await seed_transcript(client, engine, auth_headers, v2_card)
    original = await client.get(
        f"/api/sessions/{session['id']}/export",
        params={"format": "json"},
        headers=auth_headers,
    )

    response = await import_chat(client, auth_headers, character["id"], original.json())
    assert response.status_code == 201, response.text
    imported = response.json()

    assert imported["id"] != session["id"]
    assert imported["character_id"] == character["id"]
    assert imported["title"] == TITLE
    assert [message["role"] for message in imported["messages"]] == [
        "assistant",
        "user",
        "assistant",
    ]
    assert all(message["id"] > 0 for message in imported["messages"])
    assert [message["content"] for message in imported["messages"]] == [
        "Hi!",
        "Who are you?",
        "Fine, whatever.",
    ]
    assert [message["is_greeting"] for message in imported["messages"]] == [True, False, False]
    # Every assistant line belongs to the only cast member.
    assert [message["speaker_id"] for message in imported["messages"]] == [
        character["id"],
        None,
        character["id"],
    ]


async def test_import_keeps_the_transcript_timestamps(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)

    response = await import_chat(client, auth_headers, character["id"], message_list_payload())
    assert response.status_code == 201, response.text
    imported = response.json()

    assert imported["created_at"].startswith("2026-08-30T16:23:33")
    assert imported["updated_at"].startswith("2026-08-30T16:34:07")
    assert [message["created_at"][:19] for message in imported["messages"]] == [
        "2026-08-30T16:23:33",
        "2026-08-30T16:26:30",
        "2026-08-30T16:34:07",
    ]


async def test_import_a_message_list(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)

    response = await import_chat(client, auth_headers, character["id"], message_list_payload())
    assert response.status_code == 201, response.text
    imported = response.json()

    assert imported["title"] == TITLE
    assert [message["role"] for message in imported["messages"]] == [
        "assistant",
        "user",
        "assistant",
    ]
    # The greeting is the exported one, not a duplicate added on top.
    assert imported["messages"][0]["is_greeting"] is True
    assert imported["messages"][0]["content"] == message_list_payload()["greeting"]
    # Its speakers are not separate characters here, so they fall back to the primary.
    assert [message["speaker_id"] for message in imported["messages"]] == [
        character["id"],
        None,
        character["id"],
    ]
    assert [member["name"] for member in imported["characters"]] == [character["name"]]


async def test_import_adds_a_greeting_that_is_missing_from_the_messages(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    payload = {
        "title": "Later on",
        "greeting": "Hello there!",
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello!"},
        ],
    }

    response = await import_chat(client, auth_headers, character["id"], payload)
    assert response.status_code == 201, response.text
    imported = response.json()

    assert [message["role"] for message in imported["messages"]] == [
        "assistant",
        "user",
        "assistant",
    ]
    assert imported["messages"][0]["content"] == "Hello there!"
    assert imported["messages"][0]["is_greeting"] is True
    assert imported["messages"][1]["is_greeting"] is False


async def test_import_resolves_group_speakers_by_name(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    haruhi = await make_character(client, auth_headers, v2_card, name="Haruhi")
    mikuru = await make_character(client, auth_headers, v2_card, name="Mikuru")
    await make_character(client, auth_headers, v2_card, name="Yuki")

    response = await import_chat(client, auth_headers, haruhi["id"], export_payload())
    assert response.status_code == 201, response.text
    imported = response.json()

    # Only the characters the transcript names join the cast.
    assert [member["name"] for member in imported["characters"]] == ["Haruhi", "Mikuru"]
    assert imported["characters"][0]["is_primary"] is True
    assert [message["speaker_id"] for message in imported["messages"]] == [
        haruhi["id"],
        None,
        mikuru["id"],
    ]


async def test_import_only_uses_the_users_own_characters(
    client: AsyncClient,
    auth_headers: dict[str, str],
    v2_card: dict,
    login_as,
) -> None:
    haruhi = await make_character(client, auth_headers, v2_card, name="Haruhi")
    other = await login_as("misty@example.com")
    await make_character(client, other, v2_card, name="Mikuru")

    response = await import_chat(client, auth_headers, haruhi["id"], export_payload())
    assert response.status_code == 201, response.text
    assert [member["name"] for member in response.json()["characters"]] == ["Haruhi"]


async def test_import_rejects_unreadable_files(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)

    not_json = await import_chat(client, auth_headers, character["id"], b"not json at all")
    assert not_json.status_code == 422
    assert "Could not read the file" in not_json.json()["detail"]

    for payload in ([1, 2, 3], {"hello": "world"}, {"messages": []}, {"messages": [{}]}):
        response = await import_chat(client, auth_headers, character["id"], payload)
        assert response.status_code == 422, payload


async def test_import_targets_a_character_the_user_can_read(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, login_as
) -> None:
    private = await make_character(client, auth_headers, v2_card, name="Secret")
    other = await login_as("misty@example.com")

    response = await import_chat(client, other, private["id"], message_list_payload())
    assert response.status_code == 404


def test_timestamps_accept_iso_strings_and_epochs() -> None:
    chat = parse_chat(
        {
            "messages": [
                {"role": "user", "content": "a", "send_date": "2026-08-30T16:23:33.618Z"},
                {"role": "assistant", "content": "b", "timestamp": 1787843013618},
            ]
        }
    )
    # Both carry a timestamp, so the newer one is ordered first regardless of file order.
    assert [message.content for message in chat.messages] == ["b", "a"]
    assert chat.messages[1].created_at == datetime(2026, 8, 30, 16, 23, 33, 618000, tzinfo=UTC)
    assert chat.messages[0].created_at == datetime.fromtimestamp(1787843013.618, tz=UTC)


def test_roles_come_from_whichever_convention_the_file_uses() -> None:
    chat = parse_chat(
        {
            "messages": [
                {"name": "System", "is_system": True, "mes": "rules"},
                {"name": "Ash", "is_user": True, "mes": "hi"},
                {"name": "Haruhi", "is_user": False, "mes": "hey", "handle": "Haruhi"},
                {"role": "character", "content": "and hello"},
            ]
        }
    )
    assert [message.role for message in chat.messages] == [
        "system",
        "user",
        "assistant",
        "assistant",
    ]
    assert chat.messages[2].speaker == "Haruhi"


def test_a_file_without_messages_is_rejected() -> None:
    with pytest.raises(ChatImportError, match="no messages"):
        parse_chat({"name": "empty"})
