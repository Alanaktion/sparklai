"""Character CRUD, card import/export, and avatars."""

import json
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlmodel import select

from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
from sparklchat.models.base import utcnow
from sparklchat.models.card import TavernCardV2
from sparklchat.models.character import (
    Character,
    CharacterDetail,
    CharacterSummary,
    CharacterUpdate,
)
from sparklchat.services.avatars import avatar_file, delete_avatar, save_avatar
from sparklchat.services.cards import (
    CardError,
    character_detail,
    character_summary,
    dump_v1,
    dump_v2,
    parse_card,
)
from sparklchat.services.png import (
    PngError,
    blank_png,
    embed_card_json,
    is_png,
    read_card_json,
)

router = APIRouter(prefix="/characters", tags=["characters"])

ExportFormat = Literal["v1", "v2", "png"]
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


async def _owned(db: SessionDep, character_id: int, user_id: int) -> Character:
    statement = select(Character).where(Character.id == character_id, Character.user_id == user_id)
    character = (await db.exec(statement)).first()
    if character is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character


def _parse(payload: dict[str, Any]) -> tuple[TavernCardV2, str]:
    try:
        return parse_card(payload)
    except CardError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _build(card: TavernCardV2, source: str, user_id: int, avatar_path: str | None) -> Character:
    return Character(
        user_id=user_id,
        name=card.data.name,
        spec_version=card.spec_version,
        source=source,
        card_json=dump_v2(card),
        avatar_path=avatar_path,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_character(
    payload: Annotated[dict[str, Any], Body()],
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CharacterDetail:
    """Create a character from a V1 or V2 card body."""
    card, source = _parse(payload)
    character = _build(card, source, current_user.id, avatar_path=None)
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character_detail(character)


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
    character = _build(
        card, source, current_user.id, avatar_path=save_avatar(avatar) if avatar else None
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character_detail(character)


@router.get("")
async def list_characters(
    db: SessionDep,
    current_user: CurrentUserDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CharacterSummary]:
    statement = select(Character).where(Character.user_id == current_user.id)
    if q:
        statement = statement.where(Character.name.ilike(f"%{q}%"))
    statement = statement.order_by(Character.name).offset(offset).limit(limit)
    return [character_summary(row) for row in (await db.exec(statement)).all()]


@router.get("/{character_id}")
async def get_character(
    character_id: int, db: SessionDep, current_user: CurrentUserDep
) -> CharacterDetail:
    return character_detail(await _owned(db, character_id, current_user.id))


@router.patch("/{character_id}")
async def update_character(
    character_id: int,
    payload: CharacterUpdate,
    db: SessionDep,
    current_user: CurrentUserDep,
) -> CharacterDetail:
    character = await _owned(db, character_id, current_user.id)
    if payload.card is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide a `card` to update")

    card, source = _parse(payload.card)
    character.card_json = dump_v2(card)
    character.name = card.data.name
    character.spec_version = card.spec_version
    character.source = source
    character.updated_at = utcnow()
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character_detail(character)


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(character_id: int, db: SessionDep, current_user: CurrentUserDep) -> None:
    # Chat sessions will need a policy here once they exist (block or cascade).
    character = await _owned(db, character_id, current_user.id)
    delete_avatar(character.avatar_path)
    await db.delete(character)
    await db.commit()


@router.get("/{character_id}/avatar")
async def get_avatar(
    character_id: int, db: SessionDep, current_user: CurrentUserDep
) -> FileResponse:
    character = await _owned(db, character_id, current_user.id)
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
    character = await _owned(db, character_id, current_user.id)

    if export_format == "png":
        base = _avatar_bytes(character) or blank_png()
        png = embed_card_json(base, character.card_json)
        return Response(
            png,
            media_type="image/png",
            headers=_attachment(_filename(character.name, "png")),
        )

    if export_format == "v1":
        card = TavernCardV2.model_validate(character.card_json)
        return _json_download(dump_v1(card), _filename(character.name, "json"))

    return _json_download(character.card_json, _filename(character.name, "json"))


def _avatar_bytes(character: Character) -> bytes | None:
    if not character.avatar_path:
        return None
    path = avatar_file(character.avatar_path)
    return path.read_bytes() if path.is_file() else None


def _json_download(payload: dict[str, Any], filename: str) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers=_attachment(filename),
    )


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def _filename(name: str, extension: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "character"
    return f"{slug[:64]}.{extension}"
