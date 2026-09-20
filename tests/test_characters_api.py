"""Character CRUD, card import/export, and avatar endpoints."""

import copy
import json

from httpx import AsyncClient

from sparklchat.services.png import blank_png, embed_card_json, read_card_json


async def create(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/characters")).status_code == 401
    assert (await client.post("/api/characters", json={})).status_code == 401
    assert (
        await client.post(
            "/api/characters/upload",
            files={"files": ("haruhi.json", b"{}", "application/json")},
        )
    ).status_code == 401


async def test_create_from_v2_card(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    body = await create(client, auth_headers, v2_card)

    assert body["name"] == "Haruhi"
    assert body["spec_version"] == "2.0"
    assert body["source"] == "v2"
    assert body["tags"] == ["Anime", "school"]
    assert body["creator"] == "tests"
    assert body["character_version"] == "1.1"
    assert body["has_avatar"] is False
    assert body["card"]["data"]["character_book"]["entries"][0]["keys"] == ["brigade"]


async def test_create_from_v1_card_upconverts(
    client: AsyncClient, auth_headers: dict[str, str], v1_card: dict
) -> None:
    body = await create(client, auth_headers, v1_card)

    assert body["source"] == "v1"
    assert body["spec_version"] == "2.0"
    assert body["card"]["spec"] == "chara_card_v2"
    assert body["card"]["data"]["name"] == "Haruhi"
    assert body["card"]["data"]["tags"] == []
    # Unknown V1 keys are kept so a V1 export stays lossless.
    assert body["card"]["custom_v1_key"] == {"keep": "me"}


async def test_create_rejects_invalid_card(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    broken = copy.deepcopy(v2_card)
    broken["data"]["character_book"]["entries"][0]["keys"] = 5

    response = await client.post("/api/characters", json=broken, headers=auth_headers)
    assert response.status_code == 422
    assert "invalid character card" in response.json()["detail"]


async def test_list_and_search(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    await create(client, auth_headers, v2_card)

    second = copy.deepcopy(v2_card)
    second["data"]["name"] = "Mikuru"
    await create(client, auth_headers, second)

    listing = await client.get("/api/characters", headers=auth_headers)
    assert [c["name"] for c in listing.json()] == ["Haruhi", "Mikuru"]

    filtered = await client.get("/api/characters", params={"q": "miku"}, headers=auth_headers)
    assert [c["name"] for c in filtered.json()] == ["Mikuru"]


async def test_get_and_update(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    character_id = created["id"]

    fetched = await client.get(f"/api/characters/{character_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["card"] == created["card"]

    edited = copy.deepcopy(v2_card)
    edited["data"]["name"] = "Haruhi Suzumiya"
    edited["data"]["tags"] = ["renamed"]

    updated = await client.patch(
        f"/api/characters/{character_id}", json={"card": edited}, headers=auth_headers
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Haruhi Suzumiya"
    assert body["tags"] == ["renamed"]
    assert body["created_at"]


async def test_update_requires_a_card(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.patch(f"/api/characters/{created['id']}", json={}, headers=auth_headers)
    assert response.status_code == 422


async def test_delete(client: AsyncClient, auth_headers: dict[str, str], v2_card: dict) -> None:
    created = await create(client, auth_headers, v2_card)
    character_id = created["id"]

    response = await client.delete(f"/api/characters/{character_id}", headers=auth_headers)
    assert response.status_code == 204
    assert (
        await client.get(f"/api/characters/{character_id}", headers=auth_headers)
    ).status_code == 404


async def test_unknown_character_is_404(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    assert (await client.get("/api/characters/999", headers=auth_headers)).status_code == 404


async def test_characters_are_isolated_per_user(
    client: AsyncClient, auth_headers: dict[str, str], login_as, v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    other = await login_as("misty@example.com")

    assert (await client.get("/api/characters", headers=other)).json() == []
    assert (await client.get(f"/api/characters/{created['id']}", headers=other)).status_code == 404
    assert (
        await client.delete(f"/api/characters/{created['id']}", headers=other)
    ).status_code == 404


async def test_upload_png_card(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    png = embed_card_json(blank_png(), v2_card)
    response = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.png", png, "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    results = response.json()
    assert [result["filename"] for result in results] == ["haruhi.png"]
    assert results[0]["error"] is None
    body = results[0]["character"]
    assert body["name"] == "Haruhi"
    assert body["has_avatar"] is True

    # The UI loads the optimized WebP variant of the avatar...
    avatar = await client.get(f"/api/characters/{body['id']}/avatar", headers=auth_headers)
    assert avatar.status_code == 200
    assert avatar.headers["content-type"] == "image/webp"
    assert avatar.content.startswith(b"RIFF")

    # ...while the original PNG card is kept for export.
    exported = await client.get(
        f"/api/characters/{body['id']}/export",
        params={"format": "png"},
        headers=auth_headers,
    )
    assert exported.status_code == 200
    assert read_card_json(exported.content)["data"]["name"] == "Haruhi"


async def test_upload_imports_multiple_files_in_one_request(
    client: AsyncClient, auth_headers: dict[str, str], v1_card: dict, v2_card: dict
) -> None:
    png = embed_card_json(blank_png(), v2_card)
    response = await client.post(
        "/api/characters/upload",
        files=[
            ("files", ("haruhi.png", png, "image/png")),
            ("files", ("haruhi.json", json.dumps(v1_card).encode(), "application/json")),
            ("files", ("broken.png", b"\x89PNG\r\n\x1a\nnope", "image/png")),
        ],
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    results = response.json()
    assert [result["filename"] for result in results] == [
        "haruhi.png",
        "haruhi.json",
        "broken.png",
    ]
    # The readable files import; the broken one only reports an error.
    assert results[0]["character"]["source"] == "v2"
    assert results[1]["character"]["source"] == "v1"
    assert results[2]["character"] is None
    assert results[2]["error"]

    listing = await client.get("/api/characters", headers=auth_headers)
    assert len(listing.json()) == 2


async def test_upload_json_file(
    client: AsyncClient, auth_headers: dict[str, str], v1_card: dict
) -> None:
    response = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.json", json.dumps(v1_card).encode(), "application/json")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()[0]["character"]
    assert body["source"] == "v1"
    assert body["has_avatar"] is False


async def test_upload_reports_a_broken_png(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/characters/upload",
        files={"files": ("bad.png", b"\x89PNG\r\n\x1a\nnot-really-a-png", "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    result = response.json()[0]
    assert result["character"] is None
    assert "Could not read the file" in result["error"]


async def test_upload_reports_a_non_json_file(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/characters/upload",
        files={"files": ("notes.txt", b"just some text", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()[0]["character"] is None


async def test_avatar_missing_when_none_uploaded(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.get(f"/api/characters/{created['id']}/avatar", headers=auth_headers)
    assert response.status_code == 404


async def test_export_v1(client: AsyncClient, auth_headers: dict[str, str], v2_card: dict) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.get(
        f"/api/characters/{created['id']}/export",
        params={"format": "v1"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")

    body = response.json()
    assert set(body) == {
        "name",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
    }
    assert body["name"] == "Haruhi"


async def test_export_v2_is_canonical(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.get(f"/api/characters/{created['id']}/export", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == created["card"]


async def test_export_png_embeds_the_card(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.get(
        f"/api/characters/{created['id']}/export",
        params={"format": "png"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert read_card_json(response.content) == created["card"]


async def test_export_rejects_unknown_format(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.get(
        f"/api/characters/{created['id']}/export",
        params={"format": "yaml"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_export_png_reuses_the_avatar(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    png = embed_card_json(blank_png(), v2_card)
    uploaded = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.png", png, "image/png")},
        headers=auth_headers,
    )
    character_id = uploaded.json()[0]["character"]["id"]

    edited = copy.deepcopy(v2_card)
    edited["data"]["name"] = "Exported"
    await client.patch(
        f"/api/characters/{character_id}", json={"card": edited}, headers=auth_headers
    )

    response = await client.get(
        f"/api/characters/{character_id}/export",
        params={"format": "png"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    # The avatar is the base image, with the (updated) card re-embedded.
    assert read_card_json(response.content)["data"]["name"] == "Exported"


async def test_listing_reports_the_viewers_last_message_time(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    chatted = await create(client, auth_headers, v2_card)
    untouched = await create(client, auth_headers, copy.deepcopy(v2_card))

    listing = await client.get("/api/characters", headers=auth_headers)
    never = {item["id"]: item for item in listing.json()}
    assert never[chatted["id"]]["last_message_at"] is None

    # Starting a session seeds the greeting, which counts as a message.
    started = await client.post(
        f"/api/characters/{chatted['id']}/sessions", json={}, headers=auth_headers
    )
    assert started.status_code == 201, started.text

    listing = await client.get("/api/characters", headers=auth_headers)
    seen = {item["id"]: item for item in listing.json()}
    assert seen[chatted["id"]]["last_message_at"] is not None
    assert seen[untouched["id"]]["last_message_at"] is None


async def test_last_message_time_is_per_user(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, login_as
) -> None:
    created = await create(client, auth_headers, v2_card)
    await client.patch(
        f"/api/characters/{created['id']}", json={"is_public": True}, headers=auth_headers
    )
    await client.post(f"/api/characters/{created['id']}/sessions", json={}, headers=auth_headers)

    other = await login_as("other@example.com")
    listing = await client.get("/api/characters?scope=public", headers=other)
    assert listing.json()[0]["last_message_at"] is None
