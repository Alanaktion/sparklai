"""Chat sessions, messages, streaming, regeneration, and swipes."""

import copy
import json
from collections.abc import AsyncIterator, Sequence

from httpx import AsyncClient

from sparklchat.services.providers import ChatMessage, ProviderError


class StubClient:
    """Records the prompts it is given so tests can inspect what was sent."""

    def __init__(
        self, *, reply: str = "", chunks: Sequence[str] = (), error: str | None = None
    ) -> None:
        self.prompts: list[list[ChatMessage]] = []
        self._reply = reply
        self._chunks = chunks
        self._error = error

    async def complete(self, messages) -> str:
        self.prompts.append(list(messages))
        if self._error:
            raise ProviderError(self._error)
        return self._reply

    async def stream(self, messages) -> AsyncIterator[str]:
        self.prompts.append(list(messages))
        if self._error:
            raise ProviderError(self._error)
        for chunk in self._chunks:
            yield chunk


def install_stub(monkeypatch, **kwargs) -> StubClient:
    """Replace the chat router's client factory with a stub."""
    stub = StubClient(**kwargs)
    monkeypatch.setattr("sparklchat.api.chat.build_client", lambda config: stub)
    return stub


async def make_provider(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    body = {
        "name": "Test provider",
        "provider_type": "openai",
        "base_url": "https://api.example/v1",
        "api_key": "sk-test",
        "model": "test-model",
    }
    body.update(overrides)
    response = await client.post("/api/providers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    provider = response.json()
    await client.patch(
        "/api/settings",
        json={"default_provider_id": provider["id"]},
        headers=headers,
    )
    return provider


async def make_character(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
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


async def test_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/characters/1/sessions")).status_code == 401
    assert (await client.post("/api/characters/1/sessions", json={})).status_code == 401
    assert (await client.get("/api/sessions")).status_code == 401
    assert (await client.get("/api/sessions/1")).status_code == 401
    assert (
        await client.post("/api/sessions/1/messages", json={"content": "hi"})
    ).status_code == 401


async def test_create_session_seeds_the_greeting(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    assert session["title"] == "Haruhi"
    assert session["character_id"] == character["id"]
    assert session["provider_id"] is None
    assert session["use_character_book"] is True

    messages = session["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"
    assert messages[0]["is_greeting"] is True
    assert messages[0]["content"] == "Hi!"
    # `first_mes` plus `alternate_greetings` become swipes.
    assert messages[0]["swipe_count"] == 2


async def test_greeting_swipes_cycle_and_wrap(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    first = await client.post(
        f"/api/sessions/{session['id']}/greeting/swipe",
        json={"direction": "next"},
        headers=auth_headers,
    )
    assert first.json()["content"] == "Oh, it's you."
    assert first.json()["swipe_index"] == 1

    wrapped = await client.post(
        f"/api/sessions/{session['id']}/greeting/swipe",
        json={"direction": "next"},
        headers=auth_headers,
    )
    assert wrapped.json()["content"] == "Hi!"
    assert wrapped.json()["swipe_index"] == 0

    previous = await client.post(
        f"/api/sessions/{session['id']}/greeting/swipe",
        json={"direction": "prev"},
        headers=auth_headers,
    )
    assert previous.json()["content"] == "Oh, it's you."


async def test_sessions_are_listed_per_character(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    listing = await client.get(f"/api/characters/{character['id']}/sessions", headers=auth_headers)
    assert [item["id"] for item in listing.json()] == [session["id"]]


async def test_recent_sessions_span_characters(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    first = await make_character(client, auth_headers, v2_card)
    second_card = copy.deepcopy(v2_card)
    second_card["data"]["name"] = "Kyon"
    second = await make_character(client, auth_headers, second_card)

    older = await make_session(client, auth_headers, first["id"])
    newer = await make_session(client, auth_headers, second["id"])

    response = await client.get("/api/sessions", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [newer["id"], older["id"]]
    assert [item["character_name"] for item in items] == ["Kyon", "Haruhi"]
    assert items[0]["character_has_avatar"] is False
    # The seeded greeting is the newest (and only) message so far.
    assert items[0]["last_message"] == "Hi!"
    assert "messages" not in items[0]

    capped = await client.get("/api/sessions?limit=1", headers=auth_headers)
    assert [item["id"] for item in capped.json()] == [newer["id"]]


async def test_recent_sessions_follow_latest_activity(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    install_stub(monkeypatch, reply="Sure thing.")
    character = await make_character(client, auth_headers, v2_card)
    older = await make_session(client, auth_headers, character["id"])
    newer = await make_session(client, auth_headers, character["id"])

    # Replying in the older session makes it the most recent one again.
    sent = await client.post(
        f"/api/sessions/{older['id']}/messages", json={"content": "hi"}, headers=auth_headers
    )
    assert sent.status_code == 200, sent.text

    items = (await client.get("/api/sessions", headers=auth_headers)).json()
    assert [item["id"] for item in items] == [older["id"], newer["id"]]
    assert items[0]["last_message"] == "Sure thing."


async def test_recent_sessions_are_isolated_per_user(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, login_as
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    await make_session(client, auth_headers, character["id"])

    other = await login_as("other@example.com")
    assert (await client.get("/api/sessions", headers=other)).json() == []
    assert len((await client.get("/api/sessions", headers=auth_headers)).json()) == 1


async def test_session_updates(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    response = await client.patch(
        f"/api/sessions/{session['id']}",
        json={"title": "Renamed", "use_character_book": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.json()["use_character_book"] is False


async def test_delete_session(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    assert (
        await client.delete(f"/api/sessions/{session['id']}", headers=auth_headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    ).status_code == 404


async def test_sending_a_message_requires_a_provider(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hello"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "provider" in response.json()["detail"].lower()


async def test_send_message_persists_both_turns(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    stub = install_stub(monkeypatch, reply="Hello there.")

    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "Hi Haruhi"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["user"]["content"] == "Hi Haruhi"
    assert body["user"]["role"] == "user"
    assert body["assistant"]["content"] == "Hello there."
    assert body["assistant"]["role"] == "assistant"

    # The prompt the provider received includes the system message, the greeting
    # and the new user turn.
    sent = stub.prompts[-1]
    assert sent[0].role == "system"
    assert [message.role for message in sent[1:]] == ["assistant", "user"]
    assert sent[-1].content == "Hi Haruhi"


async def test_first_user_message_sets_the_title(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, reply="ok")

    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "What is the SOS Brigade?"},
        headers=auth_headers,
    )
    fetched = await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    assert fetched.json()["title"] == "What is the SOS Brigade?"

    # A later message must not rename the session.
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "And what about the club room?"},
        headers=auth_headers,
    )
    again = await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    assert again.json()["title"] == "What is the SOS Brigade?"


async def test_streaming_message_emits_events_and_persists(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, chunks=["Hel", "lo!"])

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/messages/stream",
        json={"content": "hi"},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: user" in payload
    assert "event: delta" in payload
    assert '"Hel"' in payload and '"lo!"' in payload
    assert "event: message" in payload
    assert "event: done" in payload

    messages = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    assert [message["content"] for message in messages] == ["Hi!", "hi", "Hello!"]


async def test_streaming_reports_provider_errors(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, error="upstream is down")

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/messages/stream",
        json={"content": "hi"},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "upstream is down" in payload
    assert "event: done" in payload


async def test_regenerate_keeps_the_original_as_a_swipe(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, reply="first reply")

    sent = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi"},
        headers=auth_headers,
    )
    assistant_id = sent.json()["assistant"]["id"]

    install_stub(monkeypatch, reply="second reply")
    regenerated = await client.post(
        f"/api/sessions/{session['id']}/regenerate", headers=auth_headers
    )
    assert regenerated.status_code == 200, regenerated.text
    body = regenerated.json()["assistant"]

    assert body["id"] == assistant_id
    assert body["content"] == "second reply"
    assert body["swipe_count"] == 2
    assert body["swipe_index"] == 1

    # Swiping back must restore the original reply.
    previous = await client.post(
        f"/api/sessions/{session['id']}/messages/{assistant_id}/swipe",
        json={"direction": "prev"},
        headers=auth_headers,
    )
    assert previous.json()["content"] == "first reply"


async def test_regenerate_streams(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, reply="original")
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi"},
        headers=auth_headers,
    )

    install_stub(monkeypatch, chunks=["re", "done"])
    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/regenerate/stream",
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: delta" in payload
    assert "event: message" in payload
    assert "redone" in payload


async def test_swiping_a_message_without_alternatives_is_rejected(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, reply="ok")

    sent = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi"},
        headers=auth_headers,
    )
    user_id = sent.json()["user"]["id"]

    response = await client.post(
        f"/api/sessions/{session['id']}/messages/{user_id}/swipe",
        json={"direction": "next"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_editing_and_deleting_messages(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, reply="ok")

    sent = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi"},
        headers=auth_headers,
    )
    message_id = sent.json()["user"]["id"]

    edited = await client.patch(
        f"/api/sessions/{session['id']}/messages/{message_id}",
        json={"content": "hi (edited)"},
        headers=auth_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == "hi (edited)"

    deleted = await client.delete(
        f"/api/sessions/{session['id']}/messages/{message_id}", headers=auth_headers
    )
    assert deleted.status_code == 204

    remaining = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    assert "hi (edited)" not in [message["content"] for message in remaining]


async def test_session_can_override_the_provider(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    other = await make_provider(client, auth_headers, name="Second provider")
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"], provider_id=other["id"])
    assert session["provider_id"] == other["id"]

    install_stub(monkeypatch, reply="ok")
    response = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi"},
        headers=auth_headers,
    )
    assert response.status_code == 200


async def test_sessions_are_isolated_per_user(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    other = await login_as("misty@example.com")

    assert (await client.get(f"/api/sessions/{session['id']}", headers=other)).status_code == 404
    assert (
        await client.get(f"/api/characters/{character['id']}/sessions", headers=other)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/sessions/{session['id']}/messages",
            json={"content": "hi"},
            headers=other,
        )
    ).status_code == 404


async def test_deleting_a_character_cascades_to_sessions(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    assert (
        await client.delete(f"/api/characters/{character['id']}", headers=auth_headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/sessions/{session['id']}", headers=auth_headers)
    ).status_code == 404


async def test_character_book_toggle_changes_the_prompt(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_provider(client, auth_headers)

    card = copy.deepcopy(v2_card)
    card["data"]["character_book"]["entries"][0]["constant"] = True
    character = await make_character(client, auth_headers, card)
    session = await make_session(client, auth_headers, character["id"])

    stub = install_stub(monkeypatch, reply="ok")
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi"},
        headers=auth_headers,
    )
    assert "The SOS Brigade." in stub.prompts[-1][0].content

    await client.patch(
        f"/api/sessions/{session['id']}",
        json={"use_character_book": False},
        headers=auth_headers,
    )
    await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "hi again"},
        headers=auth_headers,
    )
    assert "The SOS Brigade." not in stub.prompts[-1][0].content


async def test_message_payloads_are_json_serialisable(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    """The SSE payloads must be plain JSON, not pydantic objects."""
    await make_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, chunks=["x"])

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/messages/stream",
        json={"content": "hi"},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    for block in payload.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                json.loads(line[len("data:") :].strip())
