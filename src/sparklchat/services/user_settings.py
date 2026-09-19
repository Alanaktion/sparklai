"""Per-user settings helpers."""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models.user_settings import UserSettings


async def get_or_create_settings(db: AsyncSession, user_id: int) -> UserSettings:
    """Fetch a user's settings, creating a defaults row if it is missing."""
    settings = await db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings
