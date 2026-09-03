import pytest
from httpx import AsyncClient

from app.services import chat

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Dream Person",
        "description": "[Age: 27]",
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


async def _login_new_creator(client: AsyncClient, name: str = "Dream Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_ai_user(client: AsyncClient) -> int:
    imported = await client.post("/api/import-character", json=CARD)
    return imported.json()["id"]


async def test_dream_updates_memory(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    async def fake_completion(user_prompt, messages=None, model=None):
        assert user_prompt is None
        assert messages[0]["role"] == "system"
        assert "no posts" in messages[1]["content"]
        return "A freshly dreamed memory."

    monkeypatch.setattr(chat, "completion", fake_completion)

    response = await client.post(f"/api/users/{user_id}/dream")
    assert response.status_code == 200
    assert response.json()["memory"] == "A freshly dreamed memory."

    # A second dream sees the memory it just wrote as "Current Memory" context.
    async def fake_completion_sees_prior_memory(user_prompt, messages=None, model=None):
        assert "A freshly dreamed memory." in messages[1]["content"]
        return "An updated memory."

    monkeypatch.setattr(chat, "completion", fake_completion_sees_prior_memory)
    again = await client.post(f"/api/users/{user_id}/dream")
    assert again.json()["memory"] == "An updated memory."


async def test_dream_requires_ownership(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client, "Owner")
    user_id = await _create_ai_user(client)

    await _login_new_creator(client, "Someone Else")
    response = await client.post(f"/api/users/{user_id}/dream")
    assert response.status_code == 403


async def test_dream_requires_login(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    await client.delete("/api/creators/session")
    response = await client.post(f"/api/users/{user_id}/dream")
    assert response.status_code == 401
