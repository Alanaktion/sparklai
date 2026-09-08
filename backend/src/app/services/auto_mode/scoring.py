"""Pure, unit-testable relevance heuristics for auto-mode's tick algorithm.

No LLM call is involved in any of this — the LLM is only ever used to write the actual post/comment
text (via `PostService.generate_post_for_user`/`CommentService.generate_comment_for_post`). Who
posts and who comments is decided entirely by these cheap, deterministic-given-a-seed formulas.
"""

import math
import random

from app.db.models import Post, Relationship, User

_RELATIONSHIP_BOOST = 3.0
_INTEREST_BOOST_PER_MATCH = 0.5
_INTEREST_BOOST_CAP = 2.0
_RELEVANCE_MULTIPLIER_CAP = 4.0
# Each post one rank older (by id, within the recent-posts pool `engine.py` scans) is ~15% less
# likely to draw a comment than the one just above it — a geometric decay rather than a hard
# cutoff, so the pool's newest handful of posts dominate without older ones being flatly ignored.
_RECENCY_DECAY = 0.85
# Real threads don't grow forever - cap how many auto-generated comments any one post can collect.
_MIN_COMMENTS_PER_POST = 2
_MAX_COMMENTS_PER_POST = 5


def tick_probability(rate_per_day: float, interval_seconds: int) -> float:
    """Poisson-thinning: the chance this action fires at least once during one tick, given an
    expected rate of `rate_per_day` occurrences per day and a tick every `interval_seconds`. A
    longer interval doesn't systematically under- or over-fire relative to a shorter one at the
    same configured daily rate."""
    if rate_per_day <= 0 or interval_seconds <= 0:
        return 0.0
    lam = rate_per_day * interval_seconds / 86400
    return max(0.0, min(1.0, 1 - math.exp(-lam)))


def _shared_interest_count(a: list[str] | None, b: list[str] | None) -> int:
    if not a or not b:
        return 0
    a_set = {item.strip().lower() for item in a if item}
    b_set = {item.strip().lower() for item in b if item}
    return len(a_set & b_set)


def commenter_relevance_score(
    commenter: User, post: Post, author: User, relationship: Relationship | None
) -> float:
    """A flat base (so every eligible commenter always has *some* chance) plus boosts for an
    existing `Relationship` row and shared interests with the post's author."""
    score = 1.0
    if relationship is not None:
        score += _RELATIONSHIP_BOOST
    shared = _shared_interest_count(commenter.interests, author.interests)
    score += min(shared * _INTEREST_BOOST_PER_MATCH, _INTEREST_BOOST_CAP)
    return score


def recency_weight(rank: int) -> float:
    """`rank` is a post's 0-indexed position in the recent-posts pool (0 = newest, per
    `AutoModeRepository.list_recent_posts()`'s `ORDER BY id DESC`). Post id order is used as the
    recency signal directly, rather than parsing `created_at` (a plain `Text` column, not a real
    `DateTime` — see `db/models.py`'s docstring) — id order is exact and free of parsing edge
    cases. Returns a multiplier in `(0, 1]` that decays geometrically, so the tick algorithm
    favors the newest posts in the pool much more heavily than older ones, instead of treating
    every post in the pool as equally worth commenting on."""
    return _RECENCY_DECAY**rank


def max_comments_for_post(post: Post) -> int:
    """How many auto-generated comments a single post is allowed to accumulate in total, across
    every tick. Seeded by the post's own id rather than the shared `random` module, so the cap is
    stable for a given post no matter how many times/ticks it's re-evaluated, instead of drifting
    up or down each time."""
    return random.Random(post.id).randint(_MIN_COMMENTS_PER_POST, _MAX_COMMENTS_PER_POST)


def combine_relevance_into_probability(
    base_probability: float, relevance: float, recency: float = 1.0, scale: float = 1.0
) -> float:
    """Relevance and recency both multiply the frequency-derived base probability rather than
    replacing it, so `comment_frequency_per_day` stays the dominant lever — relevance pushes
    toward "more likely to comment on things related to them", recency pushes toward "more likely
    to comment on something recent than something stale"."""
    multiplier = min(relevance * scale, _RELEVANCE_MULTIPLIER_CAP)
    return max(0.0, min(1.0, base_probability * multiplier * recency))
