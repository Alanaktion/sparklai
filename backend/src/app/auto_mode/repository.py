from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Comment,
    CreatorAutoModeSettings,
    Post,
    Relationship,
    User,
    UserAutoModeSettings,
)

RECENT_POST_POOL_SIZE = 30


class AutoModeRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # --- Creator-level settings ---

    async def get_creator_settings(self, creator_id: int) -> CreatorAutoModeSettings | None:
        stmt = select(CreatorAutoModeSettings).where(
            CreatorAutoModeSettings.creator_id == creator_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_or_create_creator_settings(self, creator_id: int) -> CreatorAutoModeSettings:
        row = await self.get_creator_settings(creator_id)
        if row:
            return row
        row = CreatorAutoModeSettings(creator_id=creator_id)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def update_creator_settings(
        self, row: CreatorAutoModeSettings, fields: dict
    ) -> CreatorAutoModeSettings:
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_enabled_creator_ids(self) -> Sequence[int]:
        stmt = select(CreatorAutoModeSettings.creator_id).where(
            CreatorAutoModeSettings.enabled.is_(True)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # --- Per-user settings ---

    async def get_user(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_user_settings(self, user_id: int) -> UserAutoModeSettings | None:
        stmt = select(UserAutoModeSettings).where(UserAutoModeSettings.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_or_create_user_settings(self, user_id: int) -> UserAutoModeSettings:
        row = await self.get_user_settings(user_id)
        if row:
            return row
        row = UserAutoModeSettings(user_id=user_id)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def update_user_settings(
        self, row: UserAutoModeSettings, fields: dict
    ) -> UserAutoModeSettings:
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_active_users_with_settings_for_creator(
        self, creator_id: int
    ) -> Sequence[Row[tuple[User, UserAutoModeSettings | None]]]:
        """LEFT JOIN so users who've never customized their auto-mode settings still show up,
        paired with `None`."""
        stmt = (
            select(User, UserAutoModeSettings)
            .outerjoin(UserAutoModeSettings, UserAutoModeSettings.user_id == User.id)
            .where(User.creator_id == creator_id, User.is_active.is_(True))
        )
        result = await self._session.execute(stmt)
        return result.all()

    # --- Tick candidates ---

    async def list_recent_posts(self, limit: int = RECENT_POST_POOL_SIZE) -> Sequence[Post]:
        """Widened version of `CommentRepository.get_random_recent_post`'s "pull N in default
        order, don't `ORDER BY random()` the whole table" precedent — the tick algorithm ranks
        many candidates at once rather than picking one at random."""
        stmt = select(Post).order_by(Post.id.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_post_ids_commented_by_user(self, user_id: int) -> set[int]:
        stmt = select(Comment.post_id).where(Comment.user_id == user_id)
        result = await self._session.execute(stmt)
        return set(result.scalars().all())

    async def count_comments_by_post(self, post_ids: Sequence[int]) -> dict[int, int]:
        """Total existing comment count per post, for `scoring.max_comments_for_post()` to cap
        against. Missing keys (a post with zero comments) are the caller's responsibility, same as
        the `dict.get(..., 0)` callers already do elsewhere in `engine.py`."""
        if not post_ids:
            return {}
        stmt = (
            select(Comment.post_id, func.count())
            .where(Comment.post_id.in_(post_ids))
            .group_by(Comment.post_id)
        )
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def get_relationship(self, user_id: int, related_user_id: int) -> Relationship | None:
        stmt = select(Relationship).where(
            Relationship.user_id == user_id, Relationship.related_user_id == related_user_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    # --- Activity log ---

    async def list_recent_activity(self, creator_id: int, limit: int) -> list[dict]:
        """`created_at` is `Text`, not a real `DateTime` (see `db/models.py`'s docstring), so
        merging posts/comments newest-first is done in Python rather than a SQL `UNION`."""
        posts_stmt = (
            select(Post, User.name)
            .join(User, User.id == Post.user_id)
            .where(User.creator_id == creator_id, Post.is_auto_generated.is_(True))
            .order_by(Post.id.desc())
            .limit(limit)
        )
        comments_stmt = (
            select(Comment, User.name)
            .join(User, User.id == Comment.user_id)
            .where(User.creator_id == creator_id, Comment.is_auto_generated.is_(True))
            .order_by(Comment.id.desc())
            .limit(limit)
        )

        posts_result = await self._session.execute(posts_stmt)
        comments_result = await self._session.execute(comments_stmt)

        items: list[dict] = []
        for post, user_name in posts_result.all():
            items.append(
                {
                    "kind": "post",
                    "id": post.id,
                    "user_id": post.user_id,
                    "user_name": user_name,
                    "post_id": None,
                    "body": post.body,
                    "created_at": post.created_at,
                }
            )
        for comment, user_name in comments_result.all():
            items.append(
                {
                    "kind": "comment",
                    "id": comment.id,
                    "user_id": comment.user_id,
                    "user_name": user_name,
                    "post_id": comment.post_id,
                    "body": comment.body,
                    "created_at": comment.created_at,
                }
            )

        items.sort(key=lambda item: (item["created_at"] or "", item["id"]), reverse=True)
        return items[:limit]
