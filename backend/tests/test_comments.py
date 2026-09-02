import pytest
from httpx import AsyncClient

from app.services import chat

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Comment Person",
        "description": "[Age: 28]",
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
    signup = await client.post("/api/creators", json={"name": "Comment Tester", "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_user_and_post(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> tuple[int, int]:
    await _login_new_creator(client)
    imported = await client.post("/api/import-character", json=CARD)
    user_id = imported.json()["id"]

    async def fake_schema_completion(schema_name, *args, **kwargs):
        assert schema_name == "post"
        return {"post_text": "A post to comment on"}

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)
    created = await client.post("/api/posts")
    post_id = created.json()["post"]["id"]
    return user_id, post_id


async def test_create_comment_persists_and_returns_it(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _, post_id = await _create_user_and_post(client, monkeypatch)

    response = await client.post(f"/api/posts/{post_id}/comments", json={"message": "Nice post!"})
    assert response.status_code == 201
    body = response.json()
    assert body["body"] == "Nice post!"
    assert body["post_id"] == post_id
    assert body["user_id"] is None
    assert body["user"] is None


async def test_create_comment_rejects_blank_message(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _, post_id = await _create_user_and_post(client, monkeypatch)

    response = await client.post(f"/api/posts/{post_id}/comments", json={"message": "   "})
    assert response.status_code == 400


async def test_delete_comment(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    _, post_id = await _create_user_and_post(client, monkeypatch)
    created = await client.post(f"/api/posts/{post_id}/comments", json={"message": "delete me"})
    comment_id = created.json()["id"]

    response = await client.delete(f"/api/posts/{post_id}/comments/{comment_id}")
    assert response.status_code == 204


async def test_respond_generates_ai_comment_from_specified_user(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    user_id, post_id = await _create_user_and_post(client, monkeypatch)

    async def fake_completion(*args, **kwargs):
        return "An AI-generated reply"

    monkeypatch.setattr(chat, "completion", fake_completion)

    response = await client.post(
        f"/api/posts/{post_id}/comments/respond", json={"user_id": user_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["body"] == "An AI-generated reply"
    assert body["user_id"] == user_id
    assert body["user"]["id"] == user_id
    assert body["user"]["name"] == "Comment Person"


async def test_respond_404_for_missing_post(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    user_id, _ = await _create_user_and_post(client, monkeypatch)

    response = await client.post("/api/posts/999999/comments/respond", json={"user_id": user_id})
    assert response.status_code == 404


async def test_generate_random_comment(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _create_user_and_post(client, monkeypatch)

    async def fake_completion(*args, **kwargs):
        return "A random AI comment"

    monkeypatch.setattr(chat, "completion", fake_completion)

    response = await client.post("/api/posts/comments")
    assert response.status_code == 201
    assert response.json()["body"] == "A random AI comment"


async def test_translate_comment_caches_result(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    _, post_id = await _create_user_and_post(client, monkeypatch)
    created = await client.post(f"/api/posts/{post_id}/comments", json={"message": "Bonjour"})
    comment_id = created.json()["id"]

    calls = 0

    async def fake_translate(text: str) -> str:
        nonlocal calls
        calls += 1
        return "Hello"

    monkeypatch.setattr(chat, "translate_to_english", fake_translate)

    first = await client.post(f"/api/posts/{post_id}/comments/{comment_id}/translate")
    assert first.status_code == 200
    assert first.json() == {"body_en": "Hello"}

    second = await client.post(f"/api/posts/{post_id}/comments/{comment_id}/translate")
    assert second.status_code == 200
    assert second.json() == {"body_en": "Hello"}
    assert calls == 1


async def test_translate_comment_404_for_wrong_post(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _, post_id = await _create_user_and_post(client, monkeypatch)
    created = await client.post(f"/api/posts/{post_id}/comments", json={"message": "hi"})
    comment_id = created.json()["id"]

    response = await client.post(f"/api/posts/{post_id + 1}/comments/{comment_id}/translate")
    assert response.status_code == 404
