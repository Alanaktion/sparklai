from app.core.schemas import BaseSchema


class CreatorAutoModeSettingsResponse(BaseSchema):
    enabled: bool
    tick_interval_seconds: int
    max_posts_per_tick: int
    max_comments_per_tick: int


class CreatorAutoModeSettingsUpdate(BaseSchema):
    """Partial update, same `exclude_unset` convention as `CreatorUpdate`."""

    enabled: bool | None = None
    tick_interval_seconds: int | None = None
    max_posts_per_tick: int | None = None
    max_comments_per_tick: int | None = None


class UserAutoModeSettingsResponse(BaseSchema):
    user_id: int
    auto_post_enabled: bool
    auto_comment_enabled: bool
    post_frequency_per_day: float
    comment_frequency_per_day: float


class UserAutoModeSettingsUpdate(BaseSchema):
    auto_post_enabled: bool | None = None
    auto_comment_enabled: bool | None = None
    post_frequency_per_day: float | None = None
    comment_frequency_per_day: float | None = None


class UserAutoModeItem(BaseSchema):
    """One row for the settings page's character table: identity fields plus that character's
    auto-mode settings (defaulted in `AutoModeService` when no row exists yet)."""

    user_id: int
    name: str
    image_id: int | None = None
    settings: UserAutoModeSettingsResponse


class AutoModeBundleResponse(BaseSchema):
    """`GET /api/auto-mode` — creator-level settings plus every active user's row in one call."""

    creator_settings: CreatorAutoModeSettingsResponse
    users: list[UserAutoModeItem]


class AutoModeActivityItem(BaseSchema):
    kind: str  # "post" | "comment"
    id: int
    user_id: int
    user_name: str
    post_id: int | None = None
    body: str
    created_at: str | None = None


class AutoModeActivityResponse(BaseSchema):
    items: list[AutoModeActivityItem]
