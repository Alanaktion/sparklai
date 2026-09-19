"""Chat transcript export.

The transcript is seeded directly through the session rather than by calling a
provider: exporting is a presentation concern, so these tests stay fast and
deterministic.
"""

import json

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.chat import Message

TITLE = "What is the SOS Brigade?"


async def make_character(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def seed_transcript(
    client: AsyncClient,
    engine: AsyncEngine,
    headers: dict[str, str],
    v2_card: dict,
) -> dict:
    """A character, a titled session, and one exchange."""
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
        db.add(Message(session_id=session["id"], role="user", content=TITLE))
        db.add(Message(session_id=session["id"], role="assistant", content="Fine, whatever."))
        await db.commit()

    return session


async def test_export_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/sessions/1/export")).status_code == 401


async def test_export_defaults_to_markdown(
    client: AsyncClient,
    auth_headers: dict[str, str],
    engine: AsyncEngine,
    v2_card: dict,
) -> None:
    session = await seed_transcript(client, engine, auth_headers, v2_card)

    response = await client.get(
        f"/api/sessions/{session['id']}/export", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["content-disposition"].startswith("attachment; filename=")

    body = response.text
    assert body.startswith(f"# {TITLE}")
    # The greeting, the user's turn, and the reply, in order.
    assert "**Haruhi:** Hi!" in body
    assert f"**User:** {TITLE}" in body
    assert "**Haruhi:** Fine, whatever." in body
    assert body.index("**Haruhi:** Hi!") < body.index(f"**User:** {TITLE}")


async def test_markdown_uses_the_users_display_name(
    client: AsyncClient,
    auth_headers: dict[str, str],
    engine: AsyncEngine,
    v2_card: dict,
) -> None:
    await client.patch(
        "/api/settings", json={"display_name": "Ash"}, headers=auth_headers
    )
    session = await seed_transcript(client, engine, auth_headers, v2_card)

    response = await client.get(
        f"/api/sessions/{session['id']}/export", headers=auth_headers
    )
    assert f"**Ash:** {TITLE}" in response.text


async def test_export_as_json(
    client: AsyncClient,
    auth_headers: dict[str, str],
    engine: AsyncEngine,
    v2_card: dict,
) -> None:
    session = await seed_transcript(client, engine, auth_headers, v2_card)

    response = await client.get(
        f"/api/sessions/{session['id']}/export",
        params={"format": "json"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = json.loads(response.text)

    assert payload["character"]["name"] == "Haruhi"
    assert payload["session"]["id"] == session["id"]
    assert payload["session"]["title"] == TITLE
    assert [message["role"] for message in payload["messages"]] == [
        "assistant",
        "user",
        "assistant",
    ]
    assert payload["messages"][1]["content"] == TITLE


async def test_export_rejects_an_unknown_format(
    client: AsyncClient,
    auth_headers: dict[str, str],
    engine: AsyncEngine,
    v2_card: dict,
) -> None:
    session = await seed_transcript(client, engine, auth_headers, v2_card)
    response = await client.get(
        f"/api/sessions/{session['id']}/export",
        params={"format": "pdf"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_export_is_isolated_per_user(
    client: AsyncClient,
    auth_headers: dict[str, str],
    engine: AsyncEngine,
    login_as,
    v2_card: dict,
) -> None:
    session = await seed_transcript(client, engine, auth_headers, v2_card)
    other = await login_as("misty@example.com")

    assert (
        await client.get(f"/api/sessions/{session['id']}/export", headers=other)
    ).status_code == 404
