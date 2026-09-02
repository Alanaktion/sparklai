import io

import pytest
from httpx import AsyncClient
from PIL import Image as PILImage

from app.services import chat
from app.services.sd import client as sd_client

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Avatar Person",
        "description": "[Age: 29]",
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

SAMPLE_POST_IMAGE_RESPONSE = {
    "keywords": ["brown hair", "park", "sunset"],
    "aspect_ratio": "landscape",
    "image_style": "photo",
    "negative_keywords": ["blurry"],
}


def _fake_upload_bytes() -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (4, 4), color="blue").save(buffer, format="JPEG")
    return buffer.getvalue()


async def _login_new_creator(client: AsyncClient, name: str = "Avatar Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_ai_user(client: AsyncClient, name: str = "Avatar Person") -> int:
    card = {**CARD, "data": {**CARD["data"], "name": name}}
    imported = await client.post("/api/import-character", json=card)
    return imported.json()["id"]


async def _create_post(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, user_id: int) -> int:
    async def fake_schema_completion(schema_name, *args, **kwargs):
        assert schema_name == "post"
        return {"post_text": "A test post to attach an image to"}

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)
    response = await client.post(f"/api/users/{user_id}/posts", json={})
    return response.json()["post"]["id"]


async def test_upload_avatar_sets_user_image(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    files = {"file": ("avatar.jpg", _fake_upload_bytes(), "image/jpeg")}
    response = await client.post(f"/api/users/{user_id}/image", files=files)
    assert response.status_code == 201
    image_id = response.json()["image"]["id"]

    profile = await client.get(f"/api/users/{user_id}")
    assert profile.json()["user"]["image_id"] == image_id


async def test_upload_avatar_404_for_missing_user(client: AsyncClient):
    files = {"file": ("avatar.jpg", _fake_upload_bytes(), "image/jpeg")}
    response = await client.post("/api/users/999999/image", files=files)
    assert response.status_code == 404


async def test_generate_avatar_with_explicit_prompt_does_not_set_as_avatar(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    response = await client.post(
        f"/api/users/{user_id}/image",
        data={"prompt": "a specific portrait prompt", "aspect": "portrait", "count": "2"},
    )
    assert response.status_code == 202
    jobs = response.json()
    assert len(jobs) == 2
    for job in jobs:
        assert job["prompt"] == "a specific portrait prompt"
        assert job["set_as_user_image"] is False
        assert job["width"] == 480
        assert job["height"] == 640


async def test_upload_post_image_sets_post_image(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    files = {"file": ("post.jpg", _fake_upload_bytes(), "image/jpeg")}
    response = await client.post(f"/api/posts/{post_id}/image", files=files)
    assert response.status_code == 201
    assert response.json()["image"]["id"] is not None


async def test_generate_post_image_enqueues_job(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    post_id = await _create_post(client, monkeypatch, user_id)

    async def fake_schema_completion(schema_name, *args, **kwargs):
        assert schema_name == "post_image"
        return SAMPLE_POST_IMAGE_RESPONSE

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)

    response = await client.post(f"/api/posts/{post_id}/image")
    assert response.status_code == 202
    body = response.json()
    assert body["target"] == "post_image"
    assert body["post_id"] == post_id
    assert body["prompt"] == "brown hair,park,sunset"
    assert body["negative_prompt"] == "blurry"
    assert body["width"] == 640
    assert body["height"] == 480


async def test_generate_post_image_404_for_missing_post(client: AsyncClient):
    response = await client.post("/api/posts/999999/image")
    assert response.status_code == 404


async def test_generate_post_for_user_enqueues_image_job_when_requested(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    async def fake_schema_completion(schema_name, *args, **kwargs):
        assert schema_name == "post"
        return {
            "post_text": "Had a great day at the park!",
            "image_generation": {
                "image_keywords": ["park", "sunny day", "smiling"],
                "image_style": "photo",
            },
        }

    async def fake_start_generation(request):
        # The background job's actual generation isn't what this test cares about — only that
        # `generate_post_for_user()` enqueued one at all, with the right fields.
        raise RuntimeError("not exercised by this test")

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)
    monkeypatch.setattr(sd_client, "start_generation", fake_start_generation)

    response = await client.post(f"/api/users/{user_id}/posts", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["image_job"] is not None
    assert body["image_job"]["target"] == "post_generation"
    assert body["image_job"]["prompt"] == "park,sunny day,smiling"
    assert body["image_job"]["post_id"] == body["post"]["id"]
