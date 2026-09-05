import re

from fastapi import UploadFile

from app.db.models import Creator, Image, ImageGenerationJob, User
from app.exceptions import AppException, BadRequestError, NotFoundError
from app.posts.repository import PostRepository
from app.services import chat, image_utils
from app.services.dream import DREAM_SYSTEM, MAX_CHATS, MAX_COMMENTS, MAX_POSTS, build_dream_prompt
from app.services.import_character_card import CharacterCardV2, parse_character_card
from app.users.repository import UserRepository

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

_ASPECT_DIMENSIONS = {
    "portrait": (480, 640),
    "landscape": (640, 480),
}
_NUMBERED_LINE_RE = re.compile(r"^\d+[.)]\s*")
_KEYWORD_SPLIT_RE = re.compile(r"[\n|;]+")


def _split_prompt_keywords(raw: str) -> list[str]:
    return [part.strip() for part in _KEYWORD_SPLIT_RE.sub(",", raw).split(",") if part.strip()]


def _normalize_generated_prompt(raw: str) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for part in _split_prompt_keywords(raw):
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(part)
    return ", ".join(unique[:12]) if unique else raw.strip()


def _build_user_profile_text(user: User) -> str:
    lines = [f"Name: {user.name}, age {user.age} ({user.pronouns})"]
    if user.bio:
        lines.append(f"Bio: {user.bio}")
    if user.backstory:
        lines.append(f"Backstory: {user.backstory}")
    if user.occupation:
        lines.append(f"Occupation: {user.occupation}")
    if user.location:
        loc = ", ".join(
            filter(
                None,
                [
                    user.location.get("city"),
                    user.location.get("state_province"),
                    user.location.get("country"),
                ],
            )
        )
        if loc:
            lines.append(f"Location: {loc}")
    if user.interests:
        interests = ", ".join(user.interests) if isinstance(user.interests, list) else user.interests
        lines.append(f"Interests: {interests}")
    if user.personality_traits:
        lines.append(f"Personality: {user.personality_traits}")
    if user.appearance:
        lines.append(f"Appearance: {user.appearance}")
    return "\n".join(lines)


class UserService:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    async def list_for_creator(self, creator_id: int):
        return await self._repository.list_for_creator(creator_id)

    async def get_by_id_or_raise(self, user_id: int) -> User:
        user = await self._repository.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def create_ai_user(
        self, creator: Creator, prompt: str | None, model: str | None = None
    ) -> User:
        base_prompt = "Create a new user profile."
        if prompt:
            base_prompt += "\n\n" + prompt
        else:
            base_prompt += " Do not duplicate an existing user!"
            existing = await self._repository.list_for_creator(creator.id, active_only=False)
            if existing:
                profiles = "\n".join(f"- {u.name} ({u.pronouns}): {u.bio}" for u in existing)
                base_prompt += f"\nCurrent users are:\n{profiles}"

        generated = await chat.schema_completion("user", base_prompt, model=model)
        return await self._repository.create(
            name=generated["name"],
            age=generated["age"],
            pronouns=generated["pronouns"],
            bio=generated["bio"],
            location=generated["location"],
            occupation=generated["occupation"],
            interests=generated["interests"],
            personality_traits=generated["personality_traits"],
            relationship_status=generated["relationship_status"],
            writing_style=generated["writing_style"],
            appearance=generated["appearance"],
            backstory=generated["backstory"],
            creator_id=creator.id,
        )

    async def import_character_card(self, creator: Creator, raw: dict) -> User:
        if not raw or raw.get("spec") != "chara_card_v2" or not raw.get("data"):
            raise BadRequestError("Invalid character card format — expected chara_card_v2 spec")

        card = CharacterCardV2.model_validate(raw)
        parsed = parse_character_card(card, creator.id)

        return await self._repository.create(
            name=parsed.name,
            age=parsed.age,
            pronouns=parsed.pronouns,
            bio=parsed.bio,
            location=parsed.location,
            occupation=parsed.occupation,
            interests=parsed.interests,
            personality_traits=parsed.personality_traits,
            relationship_status=parsed.relationship_status,
            writing_style=parsed.writing_style,
            appearance=parsed.appearance,
            backstory=parsed.backstory,
            additional_prompt=parsed.additional_prompt,
            scenario=parsed.scenario,
            first_mes=parsed.first_mes,
            creator_id=creator.id,
        )

    async def get_profile(
        self, user_id: int, current_creator: Creator | None, post_repository: PostRepository
    ) -> dict:
        user = await self.get_by_id_or_raise(user_id)
        is_owner = bool(current_creator and user.creator_id == current_creator.id)
        posts = await post_repository.list_by_user_for_profile(user_id)
        images = await self._repository.list_images(user_id)
        relationships = await self._repository.list_relationships_with_related(user_id)

        return {
            "id": str(user_id),
            "user": user,
            "isOwner": is_owner,
            "posts": posts,
            "images": images,
            "relationships": [
                {
                    "id": rel.related_user.id,
                    "name": rel.related_user.name,
                    "pronouns": rel.related_user.pronouns,
                    "image_id": rel.related_user.image_id,
                    "relationship_type": rel.relationship_type,
                    "description": rel.description,
                }
                for rel in relationships
            ],
        }

    async def update_user(self, user_id: int, fields: dict) -> User:
        """`fields` is already `UserUpdate.model_dump(exclude_unset=True)` from the router."""
        user = await self.get_by_id_or_raise(user_id)
        if not fields:
            return user
        return await self._repository.update(user, fields)

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_by_id_or_raise(user_id)
        await self._repository.delete(user)

    async def upload_images(self, user_id: int, files: list[UploadFile]) -> list[Image]:
        """Bulk gallery upload. Does *not* set any of these as the user's avatar — see
        `upload_avatar()` for that flow."""
        user = await self.get_by_id_or_raise(user_id)
        real_files = [f for f in files if f.filename]
        if not real_files:
            raise BadRequestError("No files uploaded")

        inserted: list[Image] = []
        for file in real_files:
            contents = await file.read()
            if len(contents) > MAX_UPLOAD_BYTES:
                raise AppException(
                    message=f'File "{file.filename}" too large (max 10MB)',
                    error_code="PAYLOAD_TOO_LARGE",
                    status_code=413,
                )
            try:
                webp_data = image_utils.to_webp(contents)
            except Exception as exc:
                raise BadRequestError(f'Invalid image file: "{file.filename}"') from exc
            inserted.append(await self._repository.add_image(user_id=user.id, data=webp_data))

        if not inserted:
            raise BadRequestError("No valid files uploaded")
        return inserted

    async def upload_avatar(self, user_id: int, contents: bytes) -> Image:
        """Sets the upload directly as the user's avatar, unlike `upload_images()`'s
        gallery-only bulk upload."""
        user = await self.get_by_id_or_raise(user_id)
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
        image = await self._repository.add_image(user_id=user.id, data=webp_data)
        await self._repository.update(user, {"image_id": image.id})
        return image

    async def generate_avatar(
        self, user_id: int, *, prompt: str, aspect: str, count: int, model: str | None = None
    ) -> list[ImageGenerationJob]:
        """Queues 1-5 profile picture jobs, either from an explicit `prompt` or (when blank) one
        LLM-written per photo, extracted from the user's own profile/appearance text."""
        user = await self.get_by_id_or_raise(user_id)
        set_user_image = prompt == ""

        if prompt == "":
            profile = _build_user_profile_text(user)
            if count == 1:
                llm_prompt = (
                    "Generate a Stable Diffusion image prompt for a natural-looking profile photo "
                    "of this person.\n"
                    "Choose an authentic setting and activity that genuinely reflects their "
                    "personality, interests, and lifestyle.\n"
                    "Extract the specific appearance details from their description — hair color "
                    "and style, eye color, skin tone, body type, clothing style, distinctive "
                    "features — and include them as the first keywords so the generated image "
                    "accurately depicts how this person actually looks.\n"
                    "Return a comma-separated keyword list of 8-12 items ordered: appearance "
                    "details first, then setting and activity, then mood and lighting.\n"
                    "No prose, no numbering — just the keyword list.\n\n" + profile
                )
                prompts = [
                    _normalize_generated_prompt(await chat.completion(llm_prompt, model=model))
                ]
            else:
                llm_prompt = (
                    f"Generate exactly {count} distinct Stable Diffusion image prompts for "
                    "profile photos of this person.\n"
                    "Each should depict a completely different setting, activity, and mood — draw "
                    "from a variety of real moments in their life.\n"
                    "Every prompt must include the same core appearance keywords (hair, eye "
                    "color, skin tone, body type) so the person looks consistent across all "
                    "photos — vary only the setting, activity, and mood.\n"
                    'Format: one comma-separated keyword list per line, numbered "1.", "2.", '
                    "etc. Each list: 8-12 keywords. No prose beyond the numbered format.\n\n"
                    + profile
                )
                raw = await chat.completion(llm_prompt, model=model)
                prompts = []
                for line in raw.split("\n"):
                    cleaned = _NUMBERED_LINE_RE.sub("", line).strip()
                    normalized = _normalize_generated_prompt(cleaned) if cleaned else ""
                    if normalized:
                        prompts.append(normalized)
                prompts = prompts[:count]
                while len(prompts) < count:
                    prompts.append(prompts[0] if prompts else "portrait photo")
        else:
            prompts = [prompt] * count

        width, height = _ASPECT_DIMENSIONS.get(aspect, (512, 512))

        jobs = []
        for one_prompt in prompts:
            jobs.append(
                await self._repository.enqueue_image_job(
                    user_id=user.id,
                    target="user_image",
                    prompt=one_prompt,
                    negative_prompt=None,
                    width=width,
                    height=height,
                    include_default_prompt=True,
                    image_style="photo",
                    set_as_user_image=set_user_image,
                )
            )
        return jobs

    async def dream(self, user_id: int, model: str | None = None) -> str:
        """Reflects on the user's recent posts/comments/chats and rewrites their `memory`
        field."""
        user = await self.get_by_id_or_raise(user_id)

        recent_posts = await self._repository.list_recent_posts(user_id, MAX_POSTS)
        recent_comments = await self._repository.list_recent_comments(user_id, MAX_COMMENTS)
        recent_chats = await self._repository.list_recent_chats(user_id, MAX_CHATS)

        user_prompt = build_dream_prompt(
            user, list(recent_posts), list(recent_comments), list(recent_chats)
        )
        updated_memory = await chat.completion(
            None,
            [
                {"role": "system", "content": DREAM_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
        )

        await self._repository.update_memory(user, updated_memory)
        return updated_memory
