"""Pure, unit-testable relevance heuristics for auto-mode's tick algorithm.

No LLM call is involved in any of this — the LLM is only ever used to write the actual post/comment
text (via `PostService.generate_post_for_user`/`CommentService.generate_comment_for_post`). Who
posts and who comments is decided entirely by these cheap, deterministic-given-a-seed formulas.
"""

import math

from app.db.models import Post, Relationship, User

_RELATIONSHIP_BOOST = 3.0
_INTEREST_BOOST_PER_MATCH = 0.5
_INTEREST_BOOST_CAP = 2.0
_RELEVANCE_MULTIPLIER_CAP = 4.0


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


def combine_relevance_into_probability(
    base_probability: float, relevance: float, scale: float = 1.0
) -> float:
    """Relevance multiplies the frequency-derived base probability rather than replacing it, so
    `comment_frequency_per_day` stays the dominant lever and relevance only pushes toward "more
    likely to comment on things related to them"."""
    multiplier = min(relevance * scale, _RELEVANCE_MULTIPLIER_CAP)
    return max(0.0, min(1.0, base_probability * multiplier))
