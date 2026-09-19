"""Per-user prompt defaults."""

from fastapi import APIRouter

from sparklchat.api.deps import CurrentUserDep
from sparklchat.db import SessionDep
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
    settings.sqlmodel_update(payload.model_dump(exclude_unset=True))
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings
