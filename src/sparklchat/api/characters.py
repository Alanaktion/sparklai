"""Character CRUD, card import/export, and avatars."""

import copy
import json
import mimetypes
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlmodel import select

from sparklchat.api.access import owned_character, readable_character
from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
from sparklchat.models.base import utcnow
from sparklchat.models.card import CharacterCard
from sparklchat.models.character import (
    Character,
    CharacterDetail,
    CharacterSummary,
    CharacterTag,
    CharacterUpdate,
)
from sparklchat.services.avatars import avatar_file, delete_avatar, save_avatar
from sparklchat.services.cards import (
    CardError,
    apply_card_metadata,
    character_detail,
    character_summary,
    dump_card,
    load_card,
    normalize_tag,
    parse_card,
    stamp_creation,
    stamp_modification,
)
from sparklchat.services.charx import CharxError, is_charx, read_charx, write_charx
from sparklchat.services.downloads import attachment_headers, download_filename
from sparklchat.services.packages import delete_package, package_bytes, save_package
from sparklchat.services.png import (
    PngError,
    blank_png,
    embed_card_json,
    is_png,
    read_asset_chunks,
    read_card_json,
)

router = APIRouter(prefix="/characters", tags=["characters"])

ExportFormat = Literal["v1", "v2", "v3", "png", "charx"]
# Named orderings for `GET /characters`. `character_version` groups the versions a
# creator publishes, oldest string first, with the name breaking ties.
SORT_ORDERS: dict[str, tuple] = {
    "name": (Character.name.asc(),),
    "created": (Character.created_at.desc(),),
    "updated": (Character.updated_at.desc(),),
    "character_version": (Character.character_version.asc(), Character.name.asc()),
}
CharacterSort = Literal["name", "created", "updated", "character_version"]
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
# Card images we are willing to pull out of a CHARX package as an avatar.
_AVATAR_EXTENSIONS = frozenset({"png", "jpeg", "jpg", "webp", "avif", "gif"})
# Content types safe to serve inline; anything else is a download.
_INLINE_PREFIXES = ("image/", "audio/", "video/")


def _parse(payload: dict[str, Any]) -> tuple[CharacterCard, str]:
    try:
        return parse_card(payload)
    except CardError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _build(
    card: CharacterCard,
    source: str,
    user_id: int,
    avatar_path: str | None,
    package_path: str | None,
) -> Character:
    return Character(
        user_id=user_id,
        source=source,
        card_json=stamp_creation(dump_card(card, "v3" if source == "v3" else "v2")),
        avatar_path=avatar_path,
        package_path=package_path,
    )


async def _save_new(
    db: SessionDep,
    card: CharacterCard,
    source: str,
    user_id: int,
    avatar_path: str | None,
    package_path: str | None = None,
) -> Character:
    character = _build(card, source, user_id, avatar_path, package_path)
    db.add(character)
    await apply_card_metadata(db, character, card)
    await db.commit()
    await db.refresh(character)
    return character


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: Annotated[dict[str, Any], Body()],
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CharacterDetail:
    """Create a character from a V1, V2, or V3 card body."""
    card, source = _parse(payload)
    character = await _save_new(db, card, source, current_user.id, None)
    return character_detail(character, current_user.id)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_character(
    file: Annotated[UploadFile, File()],
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CharacterDetail:
    """Import a character from a PNG card, a CHARX package, or a JSON file."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large")

    try:
        raw, avatar, assets, package, package_suffix = _read_upload(data)
    except (PngError, CharxError, CardError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Could not read the uploaded file: {exc}",
        ) from exc

    card, source = _parse(raw)
    if avatar is None:
        avatar = _embedded_icon(raw, assets)
    character = await _save_new(
        db,
        card,
        source,
        current_user.id,
        save_avatar(avatar, _image_suffix(avatar)) if avatar else None,
        save_package(package, package_suffix) if package else None,
    )
    return character_detail(character, current_user.id)


@router.get("")
async def list_characters(
    db: SessionDep,
    current_user: CurrentUserDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    creator: Annotated[str | None, Query(max_length=200)] = None,
    character_version: Annotated[str | None, Query(max_length=100)] = None,
    scope: Annotated[Literal["mine", "public"], Query()] = "mine",
    sort: Annotated[CharacterSort, Query()] = "name",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CharacterSummary]:
    """List characters, optionally filtered.

    `scope=mine` (the default) lists the user's own; `scope=public` lists every
    published character. `q` matches the name, and `tags` matches any of the
    given tags, ignoring case.
    """
    if scope == "public":
        statement = select(Character).where(Character.is_public.is_(True))
    else:
        statement = select(Character).where(Character.user_id == current_user.id)

    if q:
        statement = statement.where(Character.name.ilike(f"%{q}%"))
    if creator:
        statement = statement.where(Character.creator.ilike(f"%{creator}%"))
    if character_version:
        statement = statement.where(Character.character_version == character_version)

    normalized = [normalize_tag(tag) for tag in tags or []]
    normalized = [tag for tag in dict.fromkeys(normalized) if tag]
    if normalized:
        statement = statement.where(
            Character.id.in_(
                select(CharacterTag.character_id).where(CharacterTag.tag.in_(normalized))
            )
        )

    statement = statement.order_by(*SORT_ORDERS[sort]).offset(offset).limit(limit)
    return [character_summary(row, current_user.id) for row in (await db.exec(statement)).all()]


@router.get("/{character_id}")
async def get_character(
    character_id: int, db: SessionDep, current_user: CurrentUserDep
) -> CharacterDetail:
    character = await readable_character(db, character_id, current_user.id)
    return character_detail(character, current_user.id)


@router.patch("/{character_id}")
async def update_character(
    character_id: int,
    payload: CharacterUpdate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CharacterDetail:
    character = await owned_character(db, character_id, current_user.id)
    if payload.card is None and payload.is_public is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Provide a `card` or `is_public` to update",
        )

    if payload.card is not None:
        card, source = _parse(payload.card)
        character.card_json = stamp_creation(dump_card(card, "v3" if source == "v3" else "v2"))
        character.source = source
        await apply_card_metadata(db, character, card)

    if payload.is_public is not None:
        character.is_public = payload.is_public

    character.updated_at = utcnow()
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character_detail(character, current_user.id)


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(character_id: int, db: SessionDep, current_user: CurrentUserDep) -> None:
    # Sessions, messages, and tag rows all cascade from the character row.
    character = await owned_character(db, character_id, current_user.id)
    delete_avatar(character.avatar_path)
    delete_package(character.package_path)
    await db.delete(character)
    await db.commit()


@router.get("/{character_id}/avatar")
async def get_avatar(
    character_id: int, db: SessionDep, current_user: CurrentUserDep
) -> FileResponse:
    character = await readable_character(db, character_id, current_user.id)
    if not character.avatar_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character has no avatar")
    path = avatar_file(character.avatar_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avatar file is missing")
    return FileResponse(path, media_type=_guess_type(path.name))


@router.get("/{character_id}/assets/{asset_path:path}")
async def get_asset(
    character_id: int,
    asset_path: str,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> Response:
    """Serve a binary asset out of the character's stored package.

    This is what makes a card's `embeded://path` asset URIs usable in the UI.
    """
    character = await readable_character(db, character_id, current_user.id)
    blob = package_bytes(character.package_path)
    if blob is None or not is_charx(blob):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character has no stored assets")
    try:
        package = read_charx(blob)
    except CharxError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character assets are unreadable") from exc
    payload = package.asset(asset_path)
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    media_type = _guess_type(asset_path)
    return Response(
        payload,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{character_id}/export")
async def export_character(
    character_id: int,
    db: SessionDep,
    current_user: CurrentUserDep,
    export_format: Annotated[ExportFormat, Query(alias="format")] = "v2",
) -> Response:
    character = await readable_character(db, character_id, current_user.id)
    card = _load(character)

    if export_format == "png":
        payload = stamp_modification(copy.deepcopy(character.card_json))
        base = _avatar_bytes(character) or blank_png()
        png = embed_card_json(base, payload)
        return Response(
            png,
            media_type="image/png",
            headers=attachment_headers(download_filename(character.name, "png")),
        )

    if export_format == "charx":
        assets = _stored_assets(character)
        package = write_charx(stamp_modification(dump_card(card, "v3")), assets)
        return Response(
            package,
            media_type="application/octet-stream",
            headers=attachment_headers(download_filename(character.name, "charx")),
        )

    exported = dump_card(card, export_format)
    if export_format == "v3":
        exported = stamp_modification(exported)
    return _json_download(exported, download_filename(character.name, "json"))
    return _json_download(dump_card(card, export_format), download_filename(character.name, "json"))


def _load(character: Character) -> CharacterCard:
    return load_card(character.card_json)


def _read_upload(
    data: bytes,
) -> tuple[dict[str, Any], bytes | None, dict[str, bytes], bytes | None, str]:
    """Classify an upload into (card JSON, avatar, assets, package, suffix)."""
    if is_charx(data):
        package = read_charx(data)
        return package.card, None, package.assets, data, ".charx"

    if is_png(data):
        raw = read_card_json(data)
        assets = read_asset_chunks(data)
        # Keep the embedded assets so `embeded://` URIs survive a re-export.
        package = write_charx(raw, assets) if assets else None
        return raw, data, assets, package, ".charx"

    raw = json.loads(data.decode("utf-8"))
    if not isinstance(raw, dict):
        raise CardError("character card must be a JSON object")
    return raw, None, {}, None, ".json"


def _embedded_icon(card_json: dict[str, Any], assets: dict[str, bytes]) -> bytes | None:
    """Pull the main `icon` asset out of a package, when it is an image."""
    candidates = _asset_entries(card_json)
    icons = [entry for entry in candidates if entry.get("type") == "icon"]
    # `name: "main"` wins, then declaration order.
    ordered = sorted(icons, key=lambda entry: entry.get("name") != "main")
    for entry in ordered:
        uri = entry.get("uri")
        ext = str(entry.get("ext") or "").lower()
        if not isinstance(uri, str) or not uri.startswith("embeded://"):
            continue
        if ext not in _AVATAR_EXTENSIONS:
            continue
        payload = assets.get(uri[len("embeded://") :])
        if payload:
            return payload
    return None


def _asset_entries(card_json: dict[str, Any]) -> list[dict[str, Any]]:
    data = card_json.get("data")
    assets = data.get("assets") if isinstance(data, dict) else None
    if not isinstance(assets, list):
        return []
    return [entry for entry in assets if isinstance(entry, dict)]


def _stored_assets(character: Character) -> dict[str, bytes]:
    blob = package_bytes(character.package_path)
    if blob is None or not is_charx(blob):
        return {}
    try:
        return read_charx(blob).assets
    except CharxError:
        return {}


def _avatar_bytes(character: Character) -> bytes | None:
    if not character.avatar_path:
        return None
    path = avatar_file(character.avatar_path)
    return path.read_bytes() if path.is_file() else None


def _image_suffix(data: bytes | None) -> str:
    """Pick a file suffix from an image's magic bytes."""
    if data is None:
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return ".avif"
    if data.startswith(b"GIF8"):
        return ".gif"
    return ".png"


def _guess_type(path: str) -> str:
    """A safe content type for a stored file name or archive path."""
    guessed = mimetypes.guess_type(path)[0] or ""
    if guessed.startswith(_INLINE_PREFIXES):
        # SVG can carry script, so it is not served inline.
        return "application/octet-stream" if guessed == "image/svg+xml" else guessed
    return guessed or "application/octet-stream"


def _json_download(payload: dict[str, Any], filename: str) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers=attachment_headers(filename),
    )
