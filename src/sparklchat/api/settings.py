"""Per-user prompt defaults and the user-level world book."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import ValidationError
from sqlmodel import select

from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
from sparklchat.models.card import CharacterBook
from sparklchat.models.provider import Provider
from sparklchat.models.user_settings import UserSettingsPublic, UserSettingsUpdate
from sparklchat.services.user_settings import get_or_create_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def read_settings(db: SessionDep, current_user: CurrentUserDep) -> UserSettingsPublic:
    return await get_or_create_settings(db, current_user.id)


@router.patch("")
async def update_settings(
    payload: UserSettingsUpdate, db: SessionDep, current_user: CurrentUserDep
) -> UserSettingsPublic:
    settings = await get_or_create_settings(db, current_user.id)
    updates = payload.model_dump(exclude_unset=True)

    # The prompt columns are NOT NULL, so an explicit null means "clear it".
    for field in ("default_system_prompt", "default_ujb"):
        if field in updates and updates[field] is None:
            updates[field] = ""
    # `display_name` is required, so an explicit null just leaves it alone.
    if updates.get("display_name") is None:
        updates.pop("display_name", None)

    provider_id = updates.get("default_provider_id")
    if provider_id is not None:
        owned = (
            await db.exec(
                select(Provider).where(
                    Provider.id == provider_id, Provider.user_id == current_user.id
                )
            )
        ).first()
        if owned is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "default_provider_id must reference one of your providers",
            )

    settings.sqlmodel_update(updates)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


@router.get("/world-book")
async def read_world_book(db: SessionDep, current_user: CurrentUserDep) -> dict[str, Any] | None:
    """The user's World Info book, or null when they have not written one."""
    settings = await get_or_create_settings(db, current_user.id)
    return settings.world_book


@router.put("/world-book")
async def replace_world_book(
    payload: Annotated[dict[str, Any], Body()],
    db: SessionDep,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """Replace the user's World Info book wholesale.

    The body is validated as a `CharacterBook` but stored verbatim, so unknown
    keys (book-level and entry-level `extensions`) survive a round trip.
    """
    try:
        CharacterBook.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Invalid world book: {exc}"
        ) from exc

    settings = await get_or_create_settings(db, current_user.id)
    settings.world_book = payload
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return payload


@router.delete("/world-book", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_book(db: SessionDep, current_user: CurrentUserDep) -> None:
    settings = await get_or_create_settings(db, current_user.id)
    settings.world_book = None
    db.add(settings)
    await db.commit()
