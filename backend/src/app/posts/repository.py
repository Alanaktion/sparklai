from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Image, ImageGenerationJob, Post, Relationship, User
from app.services.sd import jobs as sd_jobs
from app.services.sd.types import ImageGenerationJobTarget, SDStyle


class PostRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_for_creator(
        self,
        creator_id: int,
        *,
        limit: int,
        cursor: int | None,
        query: str,
    ) -> Sequence[Post]:
        active_user_ids = select(User.id).where(
            User.is_active.is_(True), User.creator_id == creator_id
        )
        stmt = select(Post).where(Post.user_id.in_(active_user_ids))
        if cursor:
            stmt = stmt.where(Post.id < cursor)
        if query:
            stmt = stmt.where(Post.body.like(f"%{query}%"))
        stmt = stmt.order_by(Post.id.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_random_active_user(self) -> User | None:
        stmt = select(User).where(User.is_active.is_(True)).order_by(func.random()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(self, user_id: int) -> Sequence[Post]:
        result = await self._session.execute(select(Post).where(Post.user_id == user_id))
        return result.scalars().all()

    async def list_by_user_for_profile(self, user_id: int) -> Sequence[Post]:
        """Newest-first, matching the profile page's `orderBy: desc(posts.created_at)` (the home
        feed instead orders by `id` — see `list_for_creator` — kept separate deliberately)."""
        stmt = select(Post).where(Post.user_id == user_id).order_by(Post.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_relationships_with_related_user(self, user_id: int) -> Sequence[Relationship]:
        result = await self._session.execute(
            select(Relationship).where(Relationship.user_id == user_id)
        )
        return result.scalars().all()

    async def create(self, *, user_id: int, body: str) -> Post:
        post = Post(user_id=user_id, body=body)
        self._session.add(post)
        await self._session.commit()
        await self._session.refresh(post)
        return post

    async def get_by_id(self, post_id: int) -> Post | None:
        return await self._session.get(Post, post_id)

    async def get_user(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def add_image(self, *, user_id: int, data: bytes) -> Image:
        image = Image(user_id=user_id, data=data)
        self._session.add(image)
        await self._session.commit()
        await self._session.refresh(image)
        return image

    async def set_image(self, post: Post, image_id: int) -> None:
        post.image_id = image_id
        await self._session.commit()

    async def enqueue_image_job(
        self,
        *,
        user_id: int,
        post_id: int | None,
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
            post_id=post_id,
            target=target,
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            include_default_prompt=include_default_prompt,
            image_style=image_style,
            set_as_user_image=set_as_user_image,
        )
