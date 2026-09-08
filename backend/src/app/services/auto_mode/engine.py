"""Auto-mode scheduler: one recurring background loop per creator with auto-mode enabled.

Mirrors `app.services.sd.jobs`'s fire-and-forget-task pattern (module-level tracking dict, an
`ensure_*_running` dedup guard, a one-shot `recover_*` call from `main.py`'s startup lifespan),
generalized to a recurring per-creator loop instead of a single one-shot job. Each tick opens its
own `AsyncSession` via `database.async_session_factory()` accessed as a module attribute (not
imported by name), which is what lets `tests/conftest.py` monkeypatch it for tests — see that
module's docstring for the full rationale.

Who posts/comments is decided by `app.services.auto_mode.scoring`'s cheap heuristics, not an LLM
call; the LLM is only used (via the existing `PostService`/`CommentService`) to write the text.
"""

import asyncio
import logging
import random

from app import database
from app.auto_mode.repository import AutoModeRepository
from app.comments.repository import CommentRepository
from app.comments.service import CommentService
from app.config import settings
from app.db.models import Post, User
from app.posts.repository import PostRepository
from app.posts.service import PostService
from app.services.auto_mode import scoring

logger = logging.getLogger(__name__)

_active_creator_loops: dict[int, asyncio.Task] = {}
_DEFAULT_INTERVAL_SECONDS = 300

# Process-wide cap on concurrent LLM/SD calls across *all* creators' loops at once, so many
# simultaneously-enabled creators (or a very short interval) can't burst the backend.
_llm_semaphore = asyncio.Semaphore(settings.auto_mode_max_concurrent_llm_calls)


def ensure_creator_loop_running(creator_id: int) -> None:
    if creator_id in _active_creator_loops:
        return
    task = asyncio.create_task(_creator_loop(creator_id))
    _active_creator_loops[creator_id] = task
    task.add_done_callback(lambda _: _active_creator_loops.pop(creator_id, None))


def stop_creator_loop(creator_id: int) -> None:
    task = _active_creator_loops.pop(creator_id, None)
    if task:
        task.cancel()


async def recover_auto_mode_loops() -> None:
    """Called once from `main.py`'s startup lifespan, mirroring `sd.jobs.recover_pending_jobs()`:
    re-attaches a loop for every creator whose settings row was left `enabled=True` by a previous
    process."""
    async with database.async_session_factory() as session:
        repo = AutoModeRepository(session)
        for creator_id in await repo.list_enabled_creator_ids():
            ensure_creator_loop_running(creator_id)


async def _creator_loop(creator_id: int) -> None:
    """The thin `while True: check; sleep; tick` wrapper. Everything else lives in
    `run_creator_tick()`, which is independently callable (no sleep involved) for tests."""
    while True:
        interval = _DEFAULT_INTERVAL_SECONDS
        try:
            async with database.async_session_factory() as session:
                repo = AutoModeRepository(session)
                creator_settings = await repo.get_creator_settings(creator_id)
                if not creator_settings or not creator_settings.enabled:
                    return  # exits; the done-callback cleans up `_active_creator_loops`
                interval = creator_settings.tick_interval_seconds
            await run_creator_tick(creator_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-mode tick failed for creator %s", creator_id)
        await asyncio.sleep(interval)


async def run_creator_tick(creator_id: int, model: str | None = None) -> dict:
    """One tick for one creator: roll each of their auto-mode-enabled characters for whether they
    post and/or comment this tick, generate content for the highest-probability rolls up to the
    creator's per-tick budget, and return a summary dict for logging/tests.

    Deliberately has no `sleep`/looping of its own so tests can call it directly and
    deterministically (e.g. by monkeypatching `random.random` in this module)."""
    async with database.async_session_factory() as session:
        repo = AutoModeRepository(session)
        creator_settings = await repo.get_or_create_creator_settings(creator_id)
        if not creator_settings.enabled:
            return {"posts_created": 0, "comments_created": 0}

        interval = creator_settings.tick_interval_seconds
        rows = await repo.list_active_users_with_settings_for_creator(creator_id)
        users_by_id: dict[int, User] = {user.id: user for user, _ in rows}

        # --- Posts ---
        post_candidates: list[tuple[User, float]] = []
        for user, user_settings in rows:
            if not user_settings or not user_settings.auto_post_enabled:
                continue
            probability = scoring.tick_probability(user_settings.post_frequency_per_day, interval)
            if random.random() < probability:
                post_candidates.append((user, probability))
        # Highest-rolled-probability-first so the budget cap favors the characters most "due" to
        # post, rather than an arbitrary/first-seen order.
        post_candidates.sort(key=lambda pair: pair[1], reverse=True)

        post_service = PostService(PostRepository(session))
        posts_created = 0
        for user, _ in post_candidates[: creator_settings.max_posts_per_tick]:
            async with _llm_semaphore:
                await post_service.generate_post_for_user(user, model=model, is_auto_generated=True)
            posts_created += 1

        # --- Comments ---
        recent_posts = await repo.list_recent_posts()
        comment_counts = await repo.count_comments_by_post([post.id for post in recent_posts])
        # Per-post cap (2-5, stable per post - see `scoring.max_comments_for_post()`) so a single
        # post's thread doesn't grow unboundedly across ticks; posts already at/over their cap are
        # skipped up front so they don't even enter the relevance-scoring below.
        comment_limits = {}
        for post in recent_posts:
            limit = scoring.max_comments_for_post(post)
            if comment_counts.get(post.id, 0) < limit:
                comment_limits[post.id] = limit
        comment_candidates: list[tuple[User, Post, float]] = []
        for user, user_settings in rows:
            if not user_settings or not user_settings.auto_comment_enabled:
                continue
            already_commented = await repo.list_post_ids_commented_by_user(user.id)
            for rank, post in enumerate(recent_posts):
                if post.id in already_commented or post.id not in comment_limits:
                    continue
                author = users_by_id.get(post.user_id) or await repo.get_user(post.user_id)
                if author is None:
                    continue
                relationship = await repo.get_relationship(user.id, post.user_id)
                relevance = scoring.commenter_relevance_score(user, post, author, relationship)
                recency = scoring.recency_weight(rank)
                base_probability = scoring.tick_probability(
                    user_settings.comment_frequency_per_day, interval
                )
                probability = scoring.combine_relevance_into_probability(
                    base_probability, relevance, recency
                )
                if random.random() < probability:
                    comment_candidates.append((user, post, probability))
        comment_candidates.sort(key=lambda triple: triple[2], reverse=True)

        comment_service = CommentService(CommentRepository(session))
        comments_created = 0
        for user, post, _ in comment_candidates:
            if comments_created >= creator_settings.max_comments_per_tick:
                break
            # Re-checked against a running count (rather than just the pre-loop snapshot) since
            # multiple candidates for the same post can both be selected within this one tick.
            if comment_counts.get(post.id, 0) >= comment_limits[post.id]:
                continue
            async with _llm_semaphore:
                await comment_service.generate_comment_for_post(
                    post, user, model=model, is_auto_generated=True
                )
            comment_counts[post.id] = comment_counts.get(post.id, 0) + 1
            comments_created += 1

        return {"posts_created": posts_created, "comments_created": comments_created}
