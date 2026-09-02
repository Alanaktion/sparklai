from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ImageGenerationJob, User


class ImageJobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_active_for_creator(self, creator_id: int) -> Sequence[ImageGenerationJob]:
        creator_user_ids = select(User.id).where(
            User.is_active.is_(True), User.creator_id == creator_id
        )
        stmt = select(ImageGenerationJob).where(
            ImageGenerationJob.user_id.in_(creator_user_ids),
            ImageGenerationJob.status.in_(["queued", "processing"]),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, job_id: int) -> ImageGenerationJob | None:
        return await self._session.get(ImageGenerationJob, job_id)
