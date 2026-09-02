import pytest
from httpx import AsyncClient

from app.services import chat

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Test Character",
        "description": "[Age: 30]\n\n[Gender: Female]",
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


async def _login_new_creator(client: AsyncClient) -> int:
    signup = await client.post("/api/creators", json={"name": "Feed Tester", "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def test_list_posts_empty_when_logged_out(client: AsyncClient):
    response = await client.get("/api/posts")
    assert response.status_code == 200
    assert response.json() == {"posts": [], "hasMore": False}


async def test_import_character_requires_auth(client: AsyncClient):
    response = await client.post("/api/import-character", json=CARD)
    assert response.status_code == 401


async def test_import_character_rejects_bad_spec(client: AsyncClient):
    await _login_new_creator(client)
    response = await client.post("/api/import-character", json={"spec": "nope"})
    assert response.status_code == 400


async def test_import_character_then_appears_in_users_list(client: AsyncClient):
    await _login_new_creator(client)

    imported = await client.post("/api/import-character", json=CARD)
    assert imported.status_code == 201
    assert imported.json()["name"] == "Test Character"
    assert imported.json()["age"] == 30

    listed = await client.get("/api/users")
    assert listed.status_code == 200
    names = [u["name"] for u in listed.json()]
    assert "Test Character" in names


async def test_create_user_calls_llm_and_persists(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)

    async def fake_schema_completion(schema_name, *args, **kwargs):
        assert schema_name == "user"
        return {
            "name": "Generated Person",
            "age": 40,
            "pronouns": "they/them",
            "bio": "A bio",
            "location": {"city": "Nowhere", "state_province": "NA", "country": "NA"},
            "occupation": "Tester",
            "interests": ["testing"],
            "personality_traits": "curious",
            "relationship_status": "Single",
            "writing_style": "terse",
            "appearance": "average",
            "backstory": "born to test",
        }

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)

    response = await client.post("/api/users", json={})
    assert response.status_code == 201
    assert response.json()["name"] == "Generated Person"


async def test_generate_post_for_random_active_user(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    await client.post("/api/import-character", json=CARD)

    async def fake_schema_completion(schema_name, *args, **kwargs):
        assert schema_name == "post"
        return {"post_text": "Hello from a generated post!"}

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)

    response = await client.post("/api/posts")
    assert response.status_code == 201
    body = response.json()
    assert body["post"]["body"] == "Hello from a generated post!"
    assert body["image_job"] is None

    feed = await client.get("/api/posts")
    assert feed.status_code == 200
    assert feed.json()["posts"][0]["body"] == "Hello from a generated post!"
