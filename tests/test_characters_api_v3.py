"""V3 card import/export, CHARX packages, and asset serving."""

import copy

from httpx import AsyncClient

from sparklchat.services.charx import read_charx
from sparklchat.services.png import blank_png, embed_card_json, read_card_json

ICON_PATH = "assets/icon/images/main.png"
ICON_BYTES = b"\x89PNG\r\n\x1a\nfake-icon"


async def create(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_from_v3_card(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    body = await create(client, auth_headers, v3_card)

    assert body["source"] == "v3"
    assert body["spec_version"] == "3.0"
    assert body["card"]["spec"] == "chara_card_v3"
    assert body["card"]["data"]["nickname"] == "Haru"
    assert body["card"]["data"]["group_only_greetings"] == ["Everyone, listen up!"]
    assert body["warnings"] == []


async def test_create_stamps_a_creation_date_when_missing(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    raw = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {"name": "Fresh", "group_only_greetings": []},
    }
    body = await create(client, auth_headers, raw)
    assert isinstance(body["card"]["data"]["creation_date"], int)


async def test_a_newer_spec_version_is_imported_with_a_warning(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    raw = copy.deepcopy(v3_card)
    raw["spec_version"] = "3.4"
    body = await create(client, auth_headers, raw)

    assert body["card"]["spec_version"] == "3.4"
    assert body["warnings"] and "newer version" in body["warnings"][0]


async def test_export_v3_keeps_v3_fields_and_stamps_modification(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    created = await create(client, auth_headers, v3_card)
    response = await client.get(
        f"/api/characters/{created['id']}/export",
        params={"format": "v3"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    exported = response.json()

    assert exported["spec"] == "chara_card_v3"
    assert exported["data"]["nickname"] == "Haru"
    assert exported["data"]["modification_date"] != 1700000100


async def test_export_v2_of_a_v3_card_drops_v3_fields(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    created = await create(client, auth_headers, v3_card)
    exported = (
        await client.get(
            f"/api/characters/{created['id']}/export",
            params={"format": "v2"},
            headers=auth_headers,
        )
    ).json()

    assert exported["spec"] == "chara_card_v2"
    assert "nickname" not in exported["data"]
    assert "assets" not in exported["data"]


async def test_export_png_of_a_v3_card_uses_the_ccv3_chunk(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    created = await create(client, auth_headers, v3_card)
    response = await client.get(
        f"/api/characters/{created['id']}/export",
        params={"format": "png"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert read_card_json(response.content)["spec"] == "chara_card_v3"


async def test_upload_charx_extracts_the_icon_and_serves_assets(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    from sparklchat.services.charx import write_charx

    package = write_charx(v3_card, {ICON_PATH: ICON_BYTES})
    response = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.charx", package, "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()[0]["character"]
    assert body["has_avatar"] is True
    assert body["card"]["data"]["assets"][0]["uri"] == f"embeded://{ICON_PATH}"

    # The icon bytes are not a real image, so there is no WebP variant and the
    # original is served.
    avatar = await client.get(f"/api/characters/{body['id']}/avatar", headers=auth_headers)
    assert avatar.status_code == 200
    assert avatar.content == ICON_BYTES

    asset = await client.get(
        f"/api/characters/{body['id']}/assets/{ICON_PATH}", headers=auth_headers
    )
    assert asset.status_code == 200
    assert asset.content == ICON_BYTES
    assert asset.headers["content-type"].startswith("image/")


async def test_export_charx_round_trips_the_package(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    from sparklchat.services.charx import write_charx

    package = write_charx(v3_card, {ICON_PATH: ICON_BYTES})
    uploaded = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.charx", package, "application/octet-stream")},
        headers=auth_headers,
    )
    character_id = uploaded.json()[0]["character"]["id"]

    response = await client.get(
        f"/api/characters/{character_id}/export",
        params={"format": "charx"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.charx"')

    exported = read_charx(response.content)
    assert exported.card["spec"] == "chara_card_v3"
    assert exported.assets[ICON_PATH] == ICON_BYTES


async def test_upload_png_keeps_embedded_asset_chunks(
    client: AsyncClient, auth_headers: dict[str, str], v3_card: dict
) -> None:
    png = with_asset_chunk(embed_card_json(blank_png(), v3_card), ICON_PATH, ICON_BYTES)
    response = await client.post(
        "/api/characters/upload",
        files={"files": ("haruhi.png", png, "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()[0]["character"]

    # The card's own assets are served through the asset endpoint; the avatar
    # endpoint hands the UI an optimized WebP copy of the image.
    avatar = await client.get(f"/api/characters/{body['id']}/avatar", headers=auth_headers)
    assert avatar.headers["content-type"] == "image/webp"

    asset = await client.get(
        f"/api/characters/{body['id']}/assets/{ICON_PATH}", headers=auth_headers
    )
    assert asset.status_code == 200
    assert asset.content == ICON_BYTES


async def test_upload_rejects_a_charx_without_card_json(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("other.txt", b"hi")

    response = await client.post(
        "/api/characters/upload",
        files={"files": ("bad.charx", buffer.getvalue(), "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    result = response.json()[0]
    assert result["character"] is None
    assert result["error"]


async def test_assets_endpoint_is_404_without_a_package(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    created = await create(client, auth_headers, v2_card)
    response = await client.get(
        f"/api/characters/{created['id']}/assets/anything.png", headers=auth_headers
    )
    assert response.status_code == 404


def with_asset_chunk(png: bytes, path: str, payload: bytes) -> bytes:
    """Append a `chara-ext-asset_:…` tEXt chunk using an independent builder."""
    import base64
    import struct
    import zlib

    from sparklchat.services.png import PNG_SIGNATURE

    keyword = f"chara-ext-asset_:{path}"
    data = keyword.encode("latin-1") + b"\x00" + base64.b64encode(payload)
    crc = zlib.crc32(b"tEXt" + data) & 0xFFFFFFFF
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data + struct.pack(">I", crc)

    assert png.startswith(PNG_SIGNATURE)
    iend = png.rindex(b"IEND") - 4  # start of the IEND length field
    return png[:iend] + chunk + png[iend:]
