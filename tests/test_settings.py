"""Per-user settings defaults, updates, and isolation."""

from httpx import AsyncClient


async def test_settings_start_with_defaults(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/settings", headers=auth_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["default_system_prompt"] == ""
    assert body["default_ujb"] == ""
    assert body["default_provider_id"] is None


async def test_settings_update_is_partial_and_persisted(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.patch(
        "/api/settings",
        headers=auth_headers,
        json={"default_system_prompt": "You are {{char}}."},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["default_system_prompt"] == "You are {{char}}."
    # Untouched fields keep their defaults.
    assert body["default_ujb"] == ""

    fetched = await client.get("/api/settings", headers=auth_headers)
    assert fetched.json()["default_system_prompt"] == "You are {{char}}."


async def test_settings_can_be_cleared_explicitly(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.patch(
        "/api/settings",
        headers=auth_headers,
        json={"default_system_prompt": "You are {{char}}."},
    )
    response = await client.patch(
        "/api/settings", headers=auth_headers, json={"default_system_prompt": None}
    )
    assert response.status_code == 200
    # The column is NOT NULL, so clearing means an empty prompt.
    assert response.json()["default_system_prompt"] == ""


async def test_settings_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/settings")).status_code == 401
    assert (await client.patch("/api/settings", json={})).status_code == 401


async def test_settings_are_isolated_per_user(
    client: AsyncClient, auth_headers: dict[str, str], password: str
) -> None:
    await client.patch("/api/settings", headers=auth_headers, json={"default_ujb": "ash's rules"})

    await client.post(
        "/api/auth/register",
        json={"email": "misty@example.com", "password": password},
    )
    login = await client.post(
        "/api/auth/login",
        data={"username": "misty@example.com", "password": password},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/settings", headers=other_headers)
    assert response.json()["default_ujb"] == ""


def _png() -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_profile_image_upload_serve_and_delete(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    assert (await client.get("/api/settings/avatar", headers=auth_headers)).status_code == 404

    response = await client.put(
        "/api/settings/avatar",
        headers=auth_headers,
        files={"file": ("me.png", _png(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["has_avatar"] is True
    assert (await client.get("/api/settings", headers=auth_headers)).json()["has_avatar"] is True

    served = await client.get("/api/settings/avatar", headers=auth_headers)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"

    original = await client.get("/api/settings/avatar/original", headers=auth_headers)
    assert original.status_code == 200
    assert original.headers["content-type"] == "image/png"
    assert original.content == _png()

    assert (await client.delete("/api/settings/avatar", headers=auth_headers)).status_code == 204
    assert (await client.get("/api/settings", headers=auth_headers)).json()["has_avatar"] is False


async def test_profile_image_rejects_non_images(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/settings/avatar",
        headers=auth_headers,
        files={"file": ("me.png", b"not an image", "image/png")},
    )
    assert response.status_code == 422
