from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Comment, Image, ImageGenerationJob, Media, Post, Relationship, User
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

    async def get_by_id_with_user(self, post_id: int) -> Post | None:
        """`Post.image`/`.media` are already `lazy="selectin"` on the model (eager-loaded either
        way); `Post.user` isn't, so the individual post page's bundle endpoint needs it loaded
        explicitly."""
        stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.user))
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_comments_for_post(self, post_id: int) -> Sequence[Comment]:
        """`Comment.user` is `lazy="selectin"` on the model, so it's eager-loaded here too without
        an explicit `.options(...)`."""
        stmt = select(Comment).where(Comment.post_id == post_id).order_by(Comment.id.asc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_images_by_user(self, user_id: int) -> Sequence[Image]:
        result = await self._session.execute(select(Image).where(Image.user_id == user_id))
        return result.scalars().all()

    async def list_media_by_user(self, user_id: int) -> Sequence[Media]:
        result = await self._session.execute(select(Media).where(Media.user_id == user_id))
        return result.scalars().all()

    async def list_active_users_for_creator(self, creator_id: int) -> Sequence[User]:
        stmt = select(User).where(User.creator_id == creator_id, User.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_user(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def update_fields(self, post: Post, fields: dict) -> Post:
        for key, value in fields.items():
            setattr(post, key, value)
        await self._session.commit()
        await self._session.refresh(post)
        return post

    async def delete(self, post: Post) -> None:
        await self._session.delete(post)
        await self._session.commit()

    async def add_media(self, *, user_id: int, media_type: str, data: bytes) -> Media:
        media = Media(user_id=user_id, type=media_type, data=data)
        self._session.add(media)
        await self._session.commit()
        await self._session.refresh(media)
        return media

    async def set_media(self, post: Post, media_id: int) -> None:
        post.media_id = media_id
        await self._session.commit()

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
