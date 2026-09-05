import json
import logging
from datetime import datetime

from app.db.models import Creator, Image, ImageGenerationJob, Post, User
from app.exceptions import AppException, BadRequestError, NotFoundError
from app.posts.repository import PostRepository
from app.services import chat, image_utils
from app.services.chat import LlamaMessage

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 15
MAX_LIMIT = 50
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB
MAX_MEDIA_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB


def _build_post_image_prompt(post_body: str, user: User) -> str:
    lines = [
        "Generate an image concept for a social media post.",
        "Be creative, but keep it believable for this person and this post.",
        "Choose a specific moment (setting + activity + mood + lighting) that feels naturally "
        "implied by the post text.",
        "Avoid generic stock-photo compositions unless the post itself suggests one.",
        "If the image features the post author, extract the relevant physical descriptors from "
        "their appearance description and include them as keywords — hair color and style, eye "
        "color, skin tone, body type, clothing style, etc.",
        "",
        f"Post body: {post_body}",
        "",
        "Author profile:",
        f"- Name: {user.name}, age {user.age} ({user.pronouns})",
    ]
    if user.bio:
        lines.append(f"- Bio: {user.bio}")
    if user.backstory:
        lines.append(f"- Backstory: {user.backstory}")
    if user.occupation:
        lines.append(f"- Occupation: {user.occupation}")
    if user.location:
        location = ", ".join(
            filter(
                None,
                [
                    user.location.get("city"),
                    user.location.get("state_province"),
                    user.location.get("country"),
                ],
            )
        )
        if location:
            lines.append(f"- Location: {location}")
    if user.interests:
        interests = (
            ", ".join(user.interests) if isinstance(user.interests, list) else user.interests
        )
        lines.append(f"- Interests: {interests}")
    if user.personality_traits:
        lines.append(f"- Personality: {user.personality_traits}")
    if user.appearance:
        lines.append(f"- Appearance: {user.appearance}")
    lines.append("")
    lines.append(
        "Return data that best fits this specific character, not a generic influencer style."
    )
    return "\n".join(lines)


_ASPECT_DIMENSIONS = {
    "portrait": (480, 640),
    "landscape": (640, 480),
}


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

    async def generate_random_post(
        self, prompt: str | None = None, model: str | None = None
    ) -> dict:
        """`POST /api/posts` — picks a random active user as author, then generates a post for
        them."""
        author = await self._repository.get_random_active_user()
        if not author:
            raise NotFoundError("No Users Found")
        return await self.generate_post_for_user(author, prompt, model)

    async def generate_post_for_user(
        self, author: User, prompt: str | None = None, model: str | None = None
    ) -> dict:
        """The actual generation logic, given an author (used directly by
        `POST /api/users/{id}/posts`, and via `generate_random_post` for `POST /api/posts`)."""
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

        response = await chat.schema_completion("post", None, history, model=model)

        post = await self._repository.create(user_id=author.id, body=response["post_text"])

        image_job = None
        image_generation = response.get("image_generation")
        if image_generation:
            try:
                # `image_keywords` is a list per the schema; join it into a comma-separated string
                # since Python won't coerce a list into a TEXT column for us.
                image_job = await self._repository.enqueue_image_job(
                    user_id=author.id,
                    post_id=post.id,
                    target="post_generation",
                    prompt=",".join(image_generation["image_keywords"]),
                    negative_prompt=None,
                    width=512,
                    height=512,
                    include_default_prompt=True,
                    image_style=image_generation.get("image_style") or "photo",
                )
            except Exception:
                logger.exception("Failed to enqueue image job for post %s", post.id)

        return {"post": post, "image_job": image_job}

    async def get_by_id_or_raise(self, post_id: int) -> Post:
        post = await self._repository.get_by_id(post_id)
        if not post:
            raise NotFoundError("Post", post_id)
        return post

    async def upload_post_image(self, post_id: int, contents: bytes) -> Image:
        post = await self.get_by_id_or_raise(post_id)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise AppException(
                message="File too large (max 10MB)",
                error_code="PAYLOAD_TOO_LARGE",
                status_code=413,
            )
        try:
            webp_data = image_utils.to_webp(contents)
        except Exception as exc:
            raise BadRequestError("Invalid image file") from exc
        image = await self._repository.add_image(user_id=post.user_id, data=webp_data)
        await self._repository.set_image(post, image.id)
        return image

    async def generate_post_image(
        self, post_id: int, model: str | None = None
    ) -> ImageGenerationJob:
        """Asks the LLM for an image concept fitting the post/author, then queues a single
        generation job."""
        post = await self.get_by_id_or_raise(post_id)
        author = await self._repository.get_user(post.user_id)
        if not author:
            raise NotFoundError("User", post.user_id)

        prompt = _build_post_image_prompt(post.body, author)
        response = await chat.schema_completion("post_image", prompt, model=model)

        negative_keywords = (
            ",".join(response["negative_keywords"]) if response.get("negative_keywords") else None
        )
        width, height = _ASPECT_DIMENSIONS.get(response.get("aspect_ratio", ""), (512, 512))

        return await self._repository.enqueue_image_job(
            user_id=author.id,
            post_id=post.id,
            target="post_image",
            prompt=",".join(response["keywords"]),
            negative_prompt=negative_keywords,
            width=width,
            height=height,
            include_default_prompt=True,
            image_style=response.get("image_style") or "photo",
        )

    async def get_bundle(self, post_id: int, creator: Creator | None) -> dict:
        """The whole individual post page bundle in one call."""
        post = await self._repository.get_by_id_with_user(post_id)
        if not post:
            raise NotFoundError("Post", post_id)
        comments = await self._repository.list_comments_for_post(post_id)

        # `PostDetailResponse` nests `user`/`comments` *inside* the post payload (unlike the
        # `Post` model, which has no ORM `comments` relationship) — assembled as a plain dict
        # rather than mutating the ORM object.
        post_payload = {
            "id": post.id,
            "user_id": post.user_id,
            "image_id": post.image_id,
            "media_id": post.media_id,
            "body": post.body,
            "body_en": post.body_en,
            "created_at": post.created_at,
            "image": post.image,
            "media": post.media,
            "user": post.user,
            "comments": comments,
        }

        if not creator:
            return {
                "id": str(post_id),
                "post": post_payload,
                "images": [],
                "media": [],
                "users": [],
            }

        return {
            "id": str(post_id),
            "post": post_payload,
            "images": await self._repository.list_images_by_user(post.user_id),
            "media": await self._repository.list_media_by_user(post.user_id),
            "users": await self._repository.list_active_users_for_creator(creator.id),
        }

    async def update_post(self, post_id: int, fields: dict) -> Post:
        """`PostUpdate`'s named fields plus a 404-on-missing-id check keep this in line with every
        other resource's PATCH in this API."""
        post = await self.get_by_id_or_raise(post_id)
        if not fields:
            return post
        return await self._repository.update_fields(post, fields)

    async def delete_post(self, post_id: int) -> None:
        """Same 404-on-missing note as `update_post`."""
        post = await self.get_by_id_or_raise(post_id)
        await self._repository.delete(post)

    async def translate_post(self, post_id: int, model: str | None = None) -> str:
        post = await self.get_by_id_or_raise(post_id)
        if post.body_en:
            return post.body_en
        body_en = await chat.translate_to_english(post.body, model=model)
        await self._repository.update_fields(post, {"body_en": body_en})
        return body_en

    async def upload_post_media(self, post_id: int, content_type: str, contents: bytes) -> dict:
        """Audio/video upload, attached to the post's author (not the post itself) and then set
        as the post's `media_id`."""
        post = await self.get_by_id_or_raise(post_id)
        if len(contents) > MAX_MEDIA_UPLOAD_BYTES:
            raise AppException(
                message="File too large (max 100MB)",
                error_code="PAYLOAD_TOO_LARGE",
                status_code=413,
            )
        if not (content_type.startswith("audio/") or content_type.startswith("video/")):
            raise BadRequestError("Only audio and video uploads are supported")

        media = await self._repository.add_media(
            user_id=post.user_id, media_type=content_type, data=contents
        )
        await self._repository.set_media(post, media.id)
        return media
