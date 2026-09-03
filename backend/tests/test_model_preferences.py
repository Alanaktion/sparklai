import pytest
from httpx import AsyncClient

from app.services import chat
from app.services.sd import client as sd_client


def _fake_fetch_chat_models(monkeypatch: pytest.MonkeyPatch, models: list[str]):
    async def fake(*args, **kwargs):
        return models

    monkeypatch.setattr(chat, "fetch_models", fake)


def _fake_fetch_sd_models(monkeypatch: pytest.MonkeyPatch, models: list[dict]):
    async def fake(*args, **kwargs):
        return models

    monkeypatch.setattr(sd_client, "fetch_models", fake)


async def test_get_defaults_with_no_cookies(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    _fake_fetch_chat_models(monkeypatch, ["model-a", "model-b"])
    _fake_fetch_sd_models(monkeypatch, [])

    response = await client.get("/api/models")
    assert response.status_code == 200
    body = response.json()
    assert body["chat_model"] in ("model-a", "model-b")
    assert body["sd_style"] == "photo"
    assert body["sd_styles"] == ["photo", "drawing", "stylized", "sdxl"]
    assert body["sd_backend"] == sd_client.backend


async def test_post_sets_chat_model_cookie(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    _fake_fetch_chat_models(monkeypatch, ["model-a", "model-b"])
    _fake_fetch_sd_models(monkeypatch, [])

    response = await client.post("/api/models", json={"chat_model": "model-b"})
    assert response.status_code == 200
    assert response.json()["chat_model"] == "model-b"
    assert client.cookies.get("chat_model") == "model-b"

    # The cookie now persists across requests.
    again = await client.get("/api/models")
    assert again.json()["chat_model"] == "model-b"


async def test_post_falls_back_when_cookie_model_unavailable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _fake_fetch_chat_models(monkeypatch, ["model-a"])
    _fake_fetch_sd_models(monkeypatch, [])

    response = await client.post("/api/models", json={"chat_model": "does-not-exist"})
    assert response.json()["chat_model"] == "model-a"


async def test_post_setting_sd_style_clears_sd_model_cookie(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _fake_fetch_chat_models(monkeypatch, ["model-a"])
    _fake_fetch_sd_models(monkeypatch, [])
    monkeypatch.setattr(sd_client, "supports_model_selection", lambda: True)

    await client.post("/api/models", json={"sd_model": "checkpoint-1"})
    assert client.cookies.get("sd_model") == "checkpoint-1"

    response = await client.post("/api/models", json={"sd_style": "drawing"})
    assert response.json()["sd_style"] == "drawing"
    assert client.cookies.get("sd_model") is None


async def test_post_omitted_keys_leave_existing_cookies_untouched(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    _fake_fetch_chat_models(monkeypatch, ["model-a", "model-b"])
    _fake_fetch_sd_models(monkeypatch, [])

    await client.post("/api/models", json={"chat_model": "model-b"})
    response = await client.post("/api/models", json={})
    assert response.json()["chat_model"] == "model-b"


async def test_chat_model_preference_used_for_generation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """The resolved `chat_model` cookie is threaded down as an explicit `model=` argument into the
    actual generation call — not just reported by the preferences endpoint."""
    seen_models = []

    async def fake_schema_completion(schema_name, *args, **kwargs):
        seen_models.append(kwargs.get("model"))
        return {
            "name": "Gen",
            "age": 30,
            "pronouns": "they/them",
            "bio": "hi",
            "location": {},
            "occupation": "",
            "interests": [],
            "personality_traits": "",
            "relationship_status": "",
            "writing_style": "",
            "appearance": "",
            "backstory": "",
        }

    monkeypatch.setattr(chat, "schema_completion", fake_schema_completion)

    signup = await client.post("/api/creators", json={"name": "Pref Tester", "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})

    client.cookies.set("chat_model", "my-preferred-model")
    await client.post("/api/users", json={})
    assert seen_models[-1] == "my-preferred-model"
