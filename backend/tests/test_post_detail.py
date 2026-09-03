import pytest
from httpx import AsyncClient

from app.services import chat

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Post Detail Person",
        "description": "[Age: 26]",
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


async def _login_new_creator(client: AsyncClient, name: str = "Post Detail Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_ai_user(client: AsyncClient) -> int:
    imported = await client.post("/api/import-character", json=CARD)
    return imported.json()["id"]


async def _create_post(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, user_id: int) -> int:
    async def fake_schema_completion(schema_name, *args, **kwargs):
        return {"post_text": "A post to look at"}

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)
    response = await client.post(f"/api/users/{user_id}/posts", json={})
    return response.json()["post"]["id"]


async def test_get_post_bundle_shape(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    response = await client.get(f"/api/posts/{post_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(post_id)
    assert body["post"]["body"] == "A post to look at"
    assert body["post"]["user"]["name"] == "Post Detail Person"
    assert body["post"]["comments"] == []
    assert body["images"] == []
    assert body["media"] == []
    assert any(u["id"] == user_id for u in body["users"])


async def test_get_post_bundle_empty_extras_when_logged_out(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)
    await client.delete("/api/creators/session")

    response = await client.get(f"/api/posts/{post_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["images"] == []
    assert body["media"] == []
    assert body["users"] == []


async def test_get_post_bundle_404_for_missing_post(client: AsyncClient):
    response = await client.get("/api/posts/999999")
    assert response.status_code == 404


async def test_patch_post_sets_and_clears_image_id(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    response = await client.patch(f"/api/posts/{post_id}", json={"image_id": None})
    assert response.status_code == 200
    assert response.json()["image_id"] is None


async def test_patch_post_404_for_missing_post(client: AsyncClient):
    response = await client.patch("/api/posts/999999", json={"image_id": None})
    assert response.status_code == 404


async def test_delete_post(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    response = await client.delete(f"/api/posts/{post_id}")
    assert response.status_code == 204

    again = await client.get(f"/api/posts/{post_id}")
    assert again.status_code == 404


async def test_translate_post_caches_result(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    calls = 0

    async def fake_translate(text: str, model: str | None = None) -> str:
        nonlocal calls
        calls += 1
        return "Translated"

    monkeypatch.setattr(chat, "translate_to_english", fake_translate)

    first = await client.post(f"/api/posts/{post_id}/translate")
    assert first.status_code == 200
    assert first.json()["body_en"] == "Translated"

    second = await client.post(f"/api/posts/{post_id}/translate")
    assert second.json()["body_en"] == "Translated"
    assert calls == 1


async def test_upload_post_media_rejects_wrong_type(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    files = {"file": ("note.txt", b"not media", "text/plain")}
    response = await client.post(f"/api/posts/{post_id}/media", files=files)
    assert response.status_code == 400


async def test_upload_post_media_sets_media_id(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    files = {"file": ("clip.webm", b"fake audio bytes", "audio/webm")}
    response = await client.post(f"/api/posts/{post_id}/media", files=files)
    assert response.status_code == 201
    media_id = response.json()["media"]["id"]

    bundle = await client.get(f"/api/posts/{post_id}")
    assert bundle.json()["post"]["media_id"] == media_id
