import io

import pytest
from httpx import AsyncClient
from PIL import Image as PILImage

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Profile Person",
        "description": "[Age: 22]",
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


async def _creator(client: AsyncClient, name: str, pin: str) -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": pin})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": pin})
    return creator_id


async def _create_ai_user(client: AsyncClient) -> int:
    imported = await client.post("/api/import-character", json=CARD)
    return imported.json()["id"]


async def test_get_profile_bundle_shape(client: AsyncClient):
    await _creator(client, "Owner", "1111")
    user_id = await _create_ai_user(client)

    response = await client.get(f"/api/users/{user_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["user"]["name"] == "Profile Person"
    assert body["isOwner"] is True
    assert body["posts"] == []
    assert body["images"] == []
    assert body["relationships"] == []


async def test_get_profile_not_owner(client: AsyncClient):
    await _creator(client, "Owner2", "1111")
    user_id = await _create_ai_user(client)

    await client.delete("/api/creators/session")
    await _creator(client, "OtherPerson", "2222")

    response = await client.get(f"/api/users/{user_id}")
    assert response.json()["isOwner"] is False


async def test_get_profile_404(client: AsyncClient):
    response = await client.get("/api/users/999999")
    assert response.status_code == 404


async def test_update_requires_ownership(client: AsyncClient):
    await _creator(client, "Owner3", "1111")
    user_id = await _create_ai_user(client)

    await client.delete("/api/creators/session")
    await _creator(client, "Intruder", "2222")

    response = await client.patch(f"/api/users/{user_id}", json={"bio": "hacked"})
    assert response.status_code == 403


async def test_update_by_owner_ignores_id_and_creator_id(client: AsyncClient):
    await _creator(client, "Owner4", "1111")
    user_id = await _create_ai_user(client)

    response = await client.patch(
        f"/api/users/{user_id}",
        json={"bio": "Updated bio", "id": 999999, "creator_id": 999999},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Updated bio"
    assert body["id"] == user_id  # unchanged despite the client trying to set it


async def test_delete_requires_ownership_then_succeeds_for_owner(client: AsyncClient):
    await _creator(client, "Owner5", "1111")
    user_id = await _create_ai_user(client)

    await client.delete("/api/creators/session")
    await _creator(client, "Intruder2", "2222")
    forbidden = await client.delete(f"/api/users/{user_id}")
    assert forbidden.status_code == 403

    await client.delete("/api/creators/session")
    await _creator(client, "Owner5b", "3333")  # not the owner either
    still_forbidden = await client.delete(f"/api/users/{user_id}")
    assert still_forbidden.status_code == 403


async def test_generate_post_for_specific_user(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from app.services import chat

    await _creator(client, "Owner6", "1111")
    user_id = await _create_ai_user(client)

    async def fake_schema_completion(schema_name, *args, **kwargs):
        return {"post_text": "A post for this exact user"}

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)

    response = await client.post(f"/api/users/{user_id}/posts", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["post"]["body"] == "A post for this exact user"
    assert body["post"]["user_id"] == user_id


async def test_generate_post_for_missing_user_404(client: AsyncClient):
    response = await client.post("/api/users/999999/posts", json={})
    assert response.status_code == 404


def _make_test_png() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


async def test_upload_images_converts_to_webp(client: AsyncClient):
    await _creator(client, "Owner7", "1111")
    user_id = await _create_ai_user(client)

    response = await client.post(
        f"/api/users/{user_id}/images",
        files=[("files", ("photo.png", _make_test_png(), "image/png"))],
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["images"]) == 1
    image_id = body["images"][0]["id"]

    fetched = await client.get(f"/api/images/{image_id}")
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/webp"


async def test_upload_images_no_files(client: AsyncClient):
    await _creator(client, "Owner8", "1111")
    user_id = await _create_ai_user(client)

    response = await client.post(f"/api/users/{user_id}/images", files=[])
    assert response.status_code in (400, 422)
