import random
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Comment, Post, Relationship, User


class CommentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_post(self, post_id: int) -> Post | None:
        return await self._session.get(Post, post_id)

    async def get_user(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_random_active_user(self) -> User | None:
        stmt = select(User).where(User.is_active.is_(True)).order_by(func.random()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_random_recent_post(self) -> Post | None:
        """Pulls (up to) 10 posts in default order, then picks one of those at random in Python,
        rather than `ORDER BY random()` on the whole table."""
        result = await self._session.execute(select(Post).limit(10))
        posts = result.scalars().all()
        return random.choice(posts) if posts else None

    async def get_relationship(self, user_id: int, related_user_id: int) -> Relationship | None:
        stmt = select(Relationship).where(
            Relationship.user_id == user_id, Relationship.related_user_id == related_user_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_post_with_commenter_name(self, post_id: int) -> Sequence[tuple[str, str | None]]:
        """Returns `(body, commenter_name)` pairs via a left join onto `users` (a comment's
        `user_id` is nullable for human, non-AI comments)."""
        stmt = (
            select(Comment.body, User.name)
            .select_from(Comment)
            .outerjoin(User, User.id == Comment.user_id)
            .where(Comment.post_id == post_id)
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def create(self, *, post_id: int, user_id: int | None, body: str) -> Comment:
        comment = Comment(post_id=post_id, user_id=user_id, body=body)
        self._session.add(comment)
        await self._session.commit()
        await self._session.refresh(comment)
        return comment

    async def get_with_user(self, comment_id: int) -> Comment | None:
        return await self._session.get(Comment, comment_id)

    async def get_by_id_and_post(self, comment_id: int, post_id: int) -> Comment | None:
        stmt = select(Comment).where(Comment.id == comment_id, Comment.post_id == post_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def update_body_en(self, comment: Comment, body_en: str) -> None:
        comment.body_en = body_en
        await self._session.commit()

    async def delete(self, comment_id: int) -> None:
        """Deletes by id alone — does not verify the comment belongs to any particular post."""
        comment = await self._session.get(Comment, comment_id)
        if comment:
            await self._session.delete(comment)
            await self._session.commit()
