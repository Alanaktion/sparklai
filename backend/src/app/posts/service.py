import json
import logging
from datetime import datetime

from app.db.models import Post, User
from app.exceptions import NotFoundError
from app.posts.repository import PostRepository
from app.services import chat
from app.services.chat import LlamaMessage

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 15
MAX_LIMIT = 50


def _build_post_prompt(user: User, datetime_str: str) -> str:
    bits = [
        f"You are generating a post for {user.name} ({user.pronouns}), age {user.age}.",
        f"Current local date/time for the character: {datetime_str}. Use this only as "
        "situational context, not as literal text to print.",
        "Write exactly like this person would post on social media.",
        "Match the user's personality, age, bio, backstory, interests, relationships, and "
        "writing style as closely as possible.",
        "Do not start with a date, time, weekday, or journal-like timestamp.",
        "Avoid generic openings, bland summaries of the day, and assistant-sounding phrasing.",
        "Vary sentence structure, pacing, and openings across posts.",
        "Keep the post grounded in concrete specifics that fit this user's life and voice.",
    ]
    if user.backstory:
        bits.append(f"Backstory: {user.backstory}")
    if user.location:
        loc = user.location
        bits.append(
            f"Location: {loc.get('city')}, {loc.get('state_province')}, {loc.get('country')}"
        )
    if user.occupation:
        bits.append(f"Occupation: {user.occupation}")
    if user.interests:
        bits.append(f"Interests: {', '.join(user.interests)}")
    if user.relationship_status:
        bits.append(f"Relationship status: {user.relationship_status}")
    if user.personality_traits:
        bits.append(f"Personality traits: {user.personality_traits}")
    if user.writing_style:
        bits.append(f"Writing style: {user.writing_style}")
    if user.appearance:
        bits.append(f"Appearance: {user.appearance}")
    return "\n".join(bits)


class PostService:
    def __init__(self, repository: PostRepository):
        self._repository = repository

    async def list_for_creator(
        self, creator_id: int | None, *, limit: int, cursor: int | None, query: str
    ) -> tuple[list[Post], bool]:
        if creator_id is None:
            return [], False
        limit = min(max(limit, 1), MAX_LIMIT)
        rows = await self._repository.list_for_creator(
            creator_id, limit=limit + 1, cursor=cursor, query=query
        )
        has_more = len(rows) > limit
        return (list(rows[:limit]) if has_more else list(rows)), has_more

    async def generate_random_post(self, prompt: str | None = None) -> dict:
        """`POST /api/posts` — port of the random-author-pick half of the original
        `(app)/posts/+server.ts` POST handler."""
        author = await self._repository.get_random_active_user()
        if not author:
            raise NotFoundError("No Users Found")
        return await self.generate_post_for_user(author, prompt)

    async def generate_post_for_user(self, author: User, prompt: str | None = None) -> dict:
        """Port of `generatePost()` in `src/lib/server/index.ts` — the actual generation logic,
        given an author (used directly by `POST /api/users/{id}/posts`, and via
        `generate_random_post` for `POST /api/posts`).

        Image-job enqueueing (`response.image_generation` -> `enqueueImageJob`) isn't wired up
        yet — that lands with the Stable Diffusion port (BACKEND_MIGRATION.md item 4). For now a
        post that requests an image is created without one, same as if generation had failed
        (the original also just logs and continues on enqueue failure).
        """
        now = datetime.now().strftime("%A, %B %-d, %Y, %-I:%M %p")
        content = _build_post_prompt(author, now)

        relationships = await self._repository.list_relationships_with_related_user(author.id)
        if relationships:
            parts = []
            for rel in relationships:
                related = rel.related_user
                text = f"{related.name} ({related.pronouns})"
                if rel.relationship_type:
                    text += f" - {rel.relationship_type}"
                if rel.description:
                    text += f": {rel.description}"
                parts.append(text)
            content += f"\nRelationships: {'; '.join(parts)}"

        history: list[LlamaMessage] = [{"role": "user", "content": content}]

        prior_posts = await self._repository.list_by_user(author.id)
        for post in prior_posts:
            history.append(
                {
                    "role": "assistant",
                    "content": json.dumps({"timestamp": post.created_at, "post_text": post.body}),
                }
            )

        prompt_content = (
            "Write the next post for the user. Make it feel distinct from prior posts, "
            "specific to this person, and naturally written for a social feed."
        )
        if prompt:
            prompt_content += "\n\n" + prompt
        history.append({"role": "user", "content": prompt_content})

        response = await chat.schema_completion("post", None, history)

        post = await self._repository.create(user_id=author.id, body=response["post_text"])

        if response.get("image_generation"):
            logger.info(
                "Post %s requested an image (style=%s) but image-job enqueueing isn't ported yet",
                post.id,
                response["image_generation"].get("image_style"),
            )

        return {"post": post, "image_job": None}
