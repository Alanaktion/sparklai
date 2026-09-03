import pytest
from httpx import AsyncClient

from app.services import chat

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Chat Person",
        "description": "[Age: 24]",
        "personality": "",
        "scenario": "",
        "first_mes": "",
        "mes_example": "",
        "creator_notes": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "alternate_greetings": [],
        "tags": [],
        "character_version": "",
        "avatar": "",
        "creator": "",
        "extensions": {},
    },
}


async def _login_new_creator(client: AsyncClient, name: str = "Chat Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_ai_user(client: AsyncClient) -> int:
    imported = await client.post("/api/import-character", json=CARD)
    return imported.json()["id"]


async def test_chat_context_requires_auth(client: AsyncClient):
    response = await client.get("/api/users/1/chat/context")
    assert response.status_code == 401


async def test_chat_context_get_and_put(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    initial = await client.get(f"/api/users/{user_id}/chat/context")
    assert initial.status_code == 200
    assert initial.json() == {"additional_prompt": ""}

    updated = await client.put(
        f"/api/users/{user_id}/chat/context", json={"additional_prompt": "Call them by nickname"}
    )
    assert updated.status_code == 200
    assert updated.json() == {"additional_prompt": "Call them by nickname"}

    refetched = await client.get(f"/api/users/{user_id}/chat/context")
    assert refetched.json() == {"additional_prompt": "Call them by nickname"}


async def test_list_messages_empty(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    response = await client.get(f"/api/users/{user_id}/chat/messages")
    assert response.status_code == 200
    assert response.json() == []


async def test_add_message_accepts_empty_string(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    response = await client.post(f"/api/users/{user_id}/chat/messages", json={"message": ""})
    assert response.status_code == 200
    assert response.json()["body"] == ""
    assert response.json()["role"] == "user"


async def test_add_message_missing_field_rejected(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    response = await client.post(f"/api/users/{user_id}/chat/messages", json={})
    assert response.status_code == 422


async def test_delete_message(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    created = await client.post(
        f"/api/users/{user_id}/chat/messages", json={"message": "delete me"}
    )
    message_id = created.json()["id"]

    response = await client.delete(f"/api/users/{user_id}/chat/messages/{message_id}")
    assert response.status_code == 204


async def test_translate_message_caches_result(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    created = await client.post(f"/api/users/{user_id}/chat/messages", json={"message": "Hola"})
    message_id = created.json()["id"]

    calls = 0

    async def fake_translate(text: str, model: str | None = None) -> str:
        nonlocal calls
        calls += 1
        return "Hello"

    monkeypatch.setattr(chat, "translate_to_english", fake_translate)

    first = await client.post(f"/api/users/{user_id}/chat/messages/{message_id}/translate")
    assert first.json() == {"body_en": "Hello"}
    second = await client.post(f"/api/users/{user_id}/chat/messages/{message_id}/translate")
    assert second.json() == {"body_en": "Hello"}
    assert calls == 1


async def test_respond_generates_and_persists_reply(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    await client.post(f"/api/users/{user_id}/chat/messages", json={"message": "hey there"})

    async def fake_completion(*args, **kwargs):
        return "hey! what's up"

    monkeypatch.setattr(chat, "completion", fake_completion)

    response = await client.post(f"/api/users/{user_id}/chat/respond")
    assert response.status_code == 200
    body = response.json()
    assert body["body"] == "hey! what's up"
    assert body["role"] == "assistant"
    assert body["user_id"] == user_id


async def test_respond_404_for_missing_user(client: AsyncClient):
    response = await client.post("/api/users/999999/chat/respond")
    assert response.status_code == 404


async def test_respond_includes_full_history_when_no_summary(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    await client.post(f"/api/users/{user_id}/chat/messages", json={"message": "first"})

    captured = {}

    async def fake_completion(user_prompt, messages, model=None):
        captured["messages"] = messages
        return "second"

    monkeypatch.setattr(chat, "completion", fake_completion)
    await client.post(f"/api/users/{user_id}/chat/respond")

    # system prompt + the one user message
    assert len(captured["messages"]) == 2
    assert captured["messages"][1] == {"role": "user", "content": "first"}


async def test_new_conversation_requires_active_messages(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    response = await client.post(f"/api/users/{user_id}/chat/new-conversation")
    assert response.status_code == 400


async def test_new_conversation_summarizes_and_persists_marker(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    await client.post(f"/api/users/{user_id}/chat/messages", json={"message": "hi"})

    async def fake_completion(*args, **kwargs):
        return "They said hi."

    monkeypatch.setattr(chat, "completion", fake_completion)

    response = await client.post(f"/api/users/{user_id}/chat/new-conversation")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "system"
    assert body["body"] == "Previous conversation summary:\nThey said hi."

    messages = await client.get(f"/api/users/{user_id}/chat/messages")
    assert len(messages.json()) == 2

    # A second summarize attempt has no active messages left to summarize.
    again = await client.post(f"/api/users/{user_id}/chat/new-conversation")
    assert again.status_code == 400


async def test_list_conversations_empty_when_logged_out(client: AsyncClient):
    response = await client.get("/api/chats")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_conversations_sorted_by_latest_message(client: AsyncClient):
    await _login_new_creator(client)
    first_user = await _create_ai_user(client)
    second_imported = await client.post(
        "/api/import-character",
        json={**CARD, "data": {**CARD["data"], "name": "Second Person"}},
    )
    second_user = second_imported.json()["id"]

    await client.post(f"/api/users/{first_user}/chat/messages", json={"message": "to first"})
    await client.post(f"/api/users/{second_user}/chat/messages", json={"message": "to second"})

    response = await client.get("/api/chats")
    assert response.status_code == 200
    body = response.json()
    assert [u["id"] for u in body] == [second_user, first_user]
    assert body[0]["chats"] == [{"id": body[0]["chats"][0]["id"], "body": "to second"}]
