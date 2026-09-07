from fastapi import APIRouter, Query

from app.auto_mode.repository import AutoModeRepository
from app.auto_mode.schemas import (
    AutoModeActivityResponse,
    AutoModeBundleResponse,
    CreatorAutoModeSettingsResponse,
    CreatorAutoModeSettingsUpdate,
    UserAutoModeSettingsResponse,
    UserAutoModeSettingsUpdate,
)
from app.auto_mode.service import AutoModeService
from app.dependencies import DbDep, RequireCreator

router = APIRouter(prefix="/auto-mode", tags=["auto-mode"])


def _service(db: DbDep) -> AutoModeService:
    return AutoModeService(AutoModeRepository(db))


@router.get("", response_model=AutoModeBundleResponse)
async def get_auto_mode_bundle(creator: RequireCreator, db: DbDep):
    return await _service(db).get_bundle(creator.id)


@router.patch("", response_model=CreatorAutoModeSettingsResponse)
async def update_auto_mode_settings(
    data: CreatorAutoModeSettingsUpdate, creator: RequireCreator, db: DbDep
):
    return await _service(db).update_creator_settings(creator.id, data)


@router.patch("/users/{user_id}", response_model=UserAutoModeSettingsResponse)
async def update_user_auto_mode_settings(
    user_id: int, data: UserAutoModeSettingsUpdate, creator: RequireCreator, db: DbDep
):
    return await _service(db).update_user_settings(creator.id, user_id, data)


@router.get("/activity", response_model=AutoModeActivityResponse)
async def get_auto_mode_activity(
    creator: RequireCreator, db: DbDep, limit: int = Query(30, ge=1, le=100)
):
    items = await _service(db).list_activity(creator.id, limit)
    return AutoModeActivityResponse(items=items)
