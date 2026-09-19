"""Character CRUD, card import/export, and avatars."""

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlmodel import select

from sparklchat.api.access import owned_character, readable_character
from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
from sparklchat.models.base import utcnow
from sparklchat.models.card import TavernCardV2
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
    dump_v1,
    dump_v2,
    normalize_tag,
    parse_card,
)
from sparklchat.services.downloads import attachment_headers, download_filename
from sparklchat.services.png import (
    PngError,
    blank_png,
    embed_card_json,
    is_png,
    read_card_json,
)

router = APIRouter(prefix="/characters", tags=["characters"])

ExportFormat = Literal["v1", "v2", "png"]
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


def _parse(payload: dict[str, Any]) -> tuple[TavernCardV2, str]:
    try:
        return parse_card(payload)
    except CardError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _build(card: TavernCardV2, source: str, user_id: int, avatar_path: str | None) -> Character:
    return Character(
        user_id=user_id,
        source=source,
        card_json=dump_v2(card),
        avatar_path=avatar_path,
    )


async def _save_new(
    db: SessionDep, card: TavernCardV2, source: str, user_id: int, avatar_path: str | None
) -> Character:
    character = _build(card, source, user_id, avatar_path)
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
    """Create a character from a V1 or V2 card body."""
    card, source = _parse(payload)
    character = await _save_new(db, card, source, current_user.id, None)
    return character_detail(character, current_user.id)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_character(
    file: Annotated[UploadFile, File()],
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CharacterDetail:
    """Import a character from an uploaded PNG card or JSON file."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large")

    avatar: bytes | None = None
    try:
        if is_png(data):
            avatar = data
            raw = read_card_json(data)
        else:
            raw = json.loads(data.decode("utf-8"))
    except (PngError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Could not read the uploaded file: {exc}",
        ) from exc

    card, source = _parse(raw)
    character = await _save_new(
        db,
        card,
        source,
        current_user.id,
        save_avatar(avatar) if avatar else None,
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
        character.card_json = dump_v2(card)
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
    return FileResponse(path, media_type="image/png")


@router.get("/{character_id}/export")
async def export_character(
    character_id: int,
    db: SessionDep,
    current_user: CurrentUserDep,
    export_format: Annotated[ExportFormat, Query(alias="format")] = "v2",
) -> Response:
    character = await readable_character(db, character_id, current_user.id)

    if export_format == "png":
        base = _avatar_bytes(character) or blank_png()
        png = embed_card_json(base, character.card_json)
        return Response(
            png,
            media_type="image/png",
            headers=attachment_headers(download_filename(character.name, "png")),
        )

    if export_format == "v1":
        card = TavernCardV2.model_validate(character.card_json)
        return _json_download(dump_v1(card), download_filename(character.name, "json"))

    return _json_download(character.card_json, download_filename(character.name, "json"))


def _avatar_bytes(character: Character) -> bytes | None:
    if not character.avatar_path:
        return None
    path = avatar_file(character.avatar_path)
    return path.read_bytes() if path.is_file() else None


def _json_download(payload: dict[str, Any], filename: str) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers=attachment_headers(filename),
    )
