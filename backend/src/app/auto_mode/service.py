from app.auto_mode.repository import AutoModeRepository
from app.auto_mode.schemas import (
    CreatorAutoModeSettingsUpdate,
    UserAutoModeSettingsUpdate,
)
from app.db.models import CreatorAutoModeSettings, UserAutoModeSettings
from app.exceptions import NotFoundError
from app.services.auto_mode import engine

# Defaults for a user who's never customized their auto-mode settings — mirrors the column
# defaults on `UserAutoModeSettings`, but applied without writing a row for every single user on
# every list call (a row is only created once that user's settings are actually written).
_DEFAULT_USER_SETTINGS = {
    "auto_post_enabled": False,
    "auto_comment_enabled": False,
    "post_frequency_per_day": 1.0,
    "comment_frequency_per_day": 3.0,
}


def _user_settings_payload(user_id: int, row: UserAutoModeSettings | None) -> dict:
    if row is None:
        return {"user_id": user_id, **_DEFAULT_USER_SETTINGS}
    return {
        "user_id": row.user_id,
        "auto_post_enabled": row.auto_post_enabled,
        "auto_comment_enabled": row.auto_comment_enabled,
        "post_frequency_per_day": row.post_frequency_per_day,
        "comment_frequency_per_day": row.comment_frequency_per_day,
    }


class AutoModeService:
    def __init__(self, repository: AutoModeRepository):
        self._repository = repository

    async def get_bundle(self, creator_id: int) -> dict:
        creator_settings = await self._repository.get_or_create_creator_settings(creator_id)
        rows = await self._repository.list_active_users_with_settings_for_creator(creator_id)
        users = [
            {
                "user_id": user.id,
                "name": user.name,
                "image_id": user.image_id,
                "settings": _user_settings_payload(user.id, settings_row),
            }
            for user, settings_row in rows
        ]
        return {"creator_settings": creator_settings, "users": users}

    async def update_creator_settings(
        self, creator_id: int, data: CreatorAutoModeSettingsUpdate
    ) -> CreatorAutoModeSettings:
        fields = data.model_dump(exclude_unset=True)
        row = await self._repository.get_or_create_creator_settings(creator_id)
        if fields:
            row = await self._repository.update_creator_settings(row, fields)

        # Start/stop this creator's background loop immediately on a toggle, rather than waiting
        # for the next app restart's `recover_auto_mode_loops()` pass.
        if row.enabled:
            engine.ensure_creator_loop_running(creator_id)
        else:
            engine.stop_creator_loop(creator_id)
        return row

    async def update_user_settings(
        self, creator_id: int, user_id: int, data: UserAutoModeSettingsUpdate
    ) -> UserAutoModeSettings:
        user = await self._repository.get_user(user_id)
        if not user or user.creator_id != creator_id:
            raise NotFoundError("User", user_id)

        fields = data.model_dump(exclude_unset=True)
        row = await self._repository.get_or_create_user_settings(user_id)
        if fields:
            row = await self._repository.update_user_settings(row, fields)
        return row

    async def list_activity(self, creator_id: int, limit: int) -> list[dict]:
        return await self._repository.list_recent_activity(creator_id, limit)
