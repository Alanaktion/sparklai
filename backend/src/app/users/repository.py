from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Image, ImageGenerationJob, Relationship, User
from app.services.sd import jobs as sd_jobs
from app.services.sd.types import ImageGenerationJobTarget, SDStyle


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def list_for_creator(self, creator_id: int, *, active_only: bool = True) -> Sequence[User]:
        stmt = select(User).where(User.creator_id == creator_id)
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, **fields) -> User:
        user = User(**fields)
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update(self, user: User, fields: dict) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.commit()

    async def list_images(self, user_id: int) -> Sequence[Image]:
        result = await self._session.execute(select(Image).where(Image.user_id == user_id))
        return result.scalars().all()

    async def add_image(self, *, user_id: int, data: bytes) -> Image:
        image = Image(user_id=user_id, data=data)
        self._session.add(image)
        await self._session.commit()
        await self._session.refresh(image)
        return image

    async def list_relationships_with_related(self, user_id: int) -> Sequence[Relationship]:
        """`Relationship.related_user` is `lazy="selectin"` on the model, so this is eager-loaded
        without an explicit `.options(...)` here."""
        result = await self._session.execute(
            select(Relationship).where(Relationship.user_id == user_id)
        )
        return result.scalars().all()

    async def enqueue_image_job(
        self,
        *,
        user_id: int,
        target: ImageGenerationJobTarget,
        prompt: str,
        negative_prompt: str | None = None,
        width: int | None = None,
        height: int | None = None,
        include_default_prompt: bool = True,
        image_style: SDStyle = "photo",
        set_as_user_image: bool = False,
    ) -> ImageGenerationJob:
        return await sd_jobs.enqueue_image_job(
            self._session,
            user_id=user_id,
            target=target,
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            include_default_prompt=include_default_prompt,
            image_style=image_style,
            set_as_user_image=set_as_user_image,
        )
