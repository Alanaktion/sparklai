"""The interactive character-creator assistant: service helpers and the API."""

import json
from collections.abc import AsyncIterator, Sequence

from httpx import AsyncClient

from sparklchat.services.character_creator import (
    DRAFT_MARKER,
    apply_patch,
    build_messages,
    merge_and_validate,
    split_reply,
)
from sparklchat.services.providers import ChatMessage, ProviderError


class StubClient:
    """Same shape as `test_chat_api.StubClient`, for the creator's own module."""

    def __init__(self, *, chunks: Sequence[str] = (), error: str | None = None) -> None:
        self.prompts: list[list[ChatMessage]] = []
        self._chunks = chunks
        self._error = error

    async def complete(self, messages) -> str:  # pragma: no cover - only stream is used
        self.prompts.append(list(messages))
        return "".join(self._chunks)

    async def stream(self, messages) -> AsyncIterator[str]:
        self.prompts.append(list(messages))
        if self._error:
            raise ProviderError(self._error)
        for chunk in self._chunks:
            yield chunk


def install_stub(monkeypatch, **kwargs) -> StubClient:
    stub = StubClient(**kwargs)
    monkeypatch.setattr("sparklchat.api.character_creator.build_client", lambda config: stub)
    return stub


def sse_events(payload: str) -> list[tuple[str, dict]]:
    """Parse an SSE payload into `(event, data)` pairs, mirroring the frontend's framing."""
    events = []
    for block in payload.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        name = "message"
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        events.append((name, json.loads(data)))
    return events


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
        "/api/settings", json={"default_provider_id": provider["id"]}, headers=headers
    )
    return provider


# --- Service-level helpers --------------------------------------------------


def test_split_reply_separates_text_from_patch() -> None:
    text = f'Here is a start.\n{DRAFT_MARKER}\n{{"name": "Rook"}}'
    display, patch = split_reply(text)
    assert display == "Here is a start."
    assert patch == {"name": "Rook"}


def test_split_reply_tolerates_a_fenced_patch() -> None:
    text = f'Sure thing.\n{DRAFT_MARKER}\n```json\n{{"tags": ["fantasy"]}}\n```'
    display, patch = split_reply(text)
    assert display == "Sure thing."
    assert patch == {"tags": ["fantasy"]}


def test_split_reply_is_lenient_about_a_missing_marker() -> None:
    display, patch = split_reply("Just talking, no patch here.")
    assert display == "Just talking, no patch here."
    assert patch is None


def test_split_reply_recovers_a_bare_trailing_patch_without_the_marker() -> None:
    """Regression: on a later turn the model sometimes drops the marker but
    still ends its reply with the JSON patch, which must not leak into the
    visible message."""
    text = 'Got it, updating the draft.\n{"name": "Rook", "tags": ["fantasy"]}'
    display, patch = split_reply(text)
    assert display == "Got it, updating the draft."
    assert patch == {"name": "Rook", "tags": ["fantasy"]}


def test_split_reply_recovers_a_fenced_trailing_patch_without_the_marker() -> None:
    text = 'Here you go.\n```json\n{"description": "A baker."}\n```'
    display, patch = split_reply(text)
    assert display == "Here you go."
    assert patch == {"description": "A baker."}


def test_split_reply_recovers_nested_json_without_the_marker() -> None:
    """The brace-scan must land on the outer object, not a nested one."""
    text = (
        "Adding some lore.\n"
        '{"lorebook_entries": [{"keys": ["bakery"], "content": "It smells of bread."}]}'
    )
    display, patch = split_reply(text)
    assert display == "Adding some lore."
    assert patch == {"lorebook_entries": [{"keys": ["bakery"], "content": "It smells of bread."}]}


def test_split_reply_recovers_trailing_json_despite_earlier_macro_braces() -> None:
    """`{{user}}`-style macros in the reply must not be mistaken for the patch."""
    text = 'The greeting will address {{user}} directly.\n{"first_mes": "Hello there!"}'
    display, patch = split_reply(text)
    assert display == "The greeting will address {{user}} directly."
    assert patch == {"first_mes": "Hello there!"}


def test_split_reply_recovers_a_patch_after_a_marker_whose_json_is_fenced() -> None:
    text = f'Sure.\n{DRAFT_MARKER}\nhere is the update:\n```json\n{{"name": "Rook"}}\n```'
    display, patch = split_reply(text)
    assert display == "Sure."
    assert patch == {"name": "Rook"}


def test_split_reply_is_lenient_about_malformed_json() -> None:
    text = f"Oops.\n{DRAFT_MARKER}\nnot json"
    display, patch = split_reply(text)
    assert display == "Oops."
    assert patch is None


def test_apply_patch_sets_core_fields_and_appends_lorebook_entries() -> None:
    draft = apply_patch({}, {"name": "Rook", "description": "A baker."})
    draft = apply_patch(
        draft,
        {
            "tags": ["fantasy"],
            "lorebook_entries": [{"keys": ["bakery"], "content": "The bakery is warm."}],
        },
    )
    assert draft["data"]["name"] == "Rook"
    assert draft["data"]["description"] == "A baker."
    assert draft["data"]["tags"] == ["fantasy"]
    assert draft["data"]["character_book"]["entries"] == [
        {"keys": ["bakery"], "content": "The bakery is warm.", "enabled": True}
    ]


def test_apply_patch_ignores_unrecognized_keys() -> None:
    draft = apply_patch({}, {"name": "Rook", "spec": "chara_card_v3", "made_up": "x"})
    assert draft["data"]["name"] == "Rook"
    assert draft["spec"] == "chara_card_v2"
    assert "made_up" not in draft["data"]


def test_merge_and_validate_keeps_the_previous_draft_on_bad_types() -> None:
    draft = apply_patch({}, {"name": "Rook"})
    merged, ok = merge_and_validate(draft, {"tags": "not-a-list"})
    assert ok is False
    assert merged == draft


def test_build_messages_includes_system_context_and_history() -> None:
    turns = [
        type("Turn", (), {"role": "user", "content": "a grumpy retired dragon-slayer"})(),
    ]
    messages = build_messages({"data": {"name": "Rook"}}, turns)
    assert messages[0].role == "system"
    assert DRAFT_MARKER in messages[0].content
    assert messages[1].role == "system"
    assert "Rook" in messages[1].content
    assert messages[2] == ChatMessage(role="user", content="a grumpy retired dragon-slayer")


# --- API ---------------------------------------------------------------------


async def test_stream_creator_message_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/character-creator/message/stream",
        json={"draft": {}, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 401


async def test_stream_creator_message_without_a_provider(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    async with client.stream(
        "POST",
        "/api/character-creator/message/stream",
        json={"draft": {}, "messages": [{"role": "user", "content": "a grumpy baker"}]},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])
    assert "event: error" in payload
    assert "No provider configured" in payload
    assert "event: done" in payload


async def test_stream_creator_message_emits_deltas_message_and_draft(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    reply = (
        f"Here is a first draft.\n{DRAFT_MARKER}\n"
        '{"name": "Rook", "description": "A retired dragon-slayer turned baker."}'
    )
    install_stub(monkeypatch, chunks=[reply[:20], reply[20:]])

    async with client.stream(
        "POST",
        "/api/character-creator/message/stream",
        json={"draft": {}, "messages": [{"role": "user", "content": "a grumpy baker"}]},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = "".join([chunk async for chunk in response.aiter_text()])

    events = sse_events(payload)
    assert any(name == "delta" for name, _ in events)
    message = next(data for name, data in events if name == "message")
    assert message["message"] == "Here is a first draft."
    draft = next(data for name, data in events if name == "draft")
    assert draft["draft"]["data"]["name"] == "Rook"
    assert draft["draft"]["data"]["description"] == "A retired dragon-slayer turned baker."
    assert events[-1][0] == "done"


async def test_stream_creator_message_reports_provider_errors(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    await make_provider(client, auth_headers)
    install_stub(monkeypatch, error="upstream is down")

    async with client.stream(
        "POST",
        "/api/character-creator/message/stream",
        json={"draft": {}, "messages": [{"role": "user", "content": "a grumpy baker"}]},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "upstream is down" in payload
    assert "event: done" in payload


async def test_stream_creator_message_rejects_a_provider_owned_by_someone_else(
    client: AsyncClient, auth_headers: dict[str, str], password: str, monkeypatch
) -> None:
    provider = await make_provider(client, auth_headers)
    install_stub(monkeypatch, chunks=["hi"])

    other = await client.post(
        "/api/auth/register", json={"email": "other@example.com", "password": password}
    )
    assert other.status_code == 201, other.text
    login = await client.post(
        "/api/auth/login", data={"username": "other@example.com", "password": password}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    async with client.stream(
        "POST",
        "/api/character-creator/message/stream",
        json={
            "provider_id": provider["id"],
            "draft": {},
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=other_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "No provider configured" in payload
