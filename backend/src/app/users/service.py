from fastapi import UploadFile

from app.db.models import Creator, Image, User
from app.exceptions import AppException, BadRequestError, NotFoundError
from app.posts.repository import PostRepository
from app.services import chat, image_utils
from app.services.import_character_card import CharacterCardV2, parse_character_card
from app.users.repository import UserRepository

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


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

    async def create_ai_user(self, creator: Creator, prompt: str | None) -> User:
        """Port of `(app)/users/+server.ts`'s POST handler."""
        base_prompt = "Create a new user profile."
        if prompt:
            base_prompt += "\n\n" + prompt
        else:
            base_prompt += " Do not duplicate an existing user!"
            existing = await self._repository.list_for_creator(creator.id, active_only=False)
            if existing:
                profiles = "\n".join(f"- {u.name} ({u.pronouns}): {u.bio}" for u in existing)
                base_prompt += f"\nCurrent users are:\n{profiles}"

        generated = await chat.schema_completion("user", base_prompt)
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
        """Port of `api/import-character/+server.ts`."""
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
        """Port of `users/[id]/+layout.server.ts`'s load."""
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
        """Port of `users/[id]/+server.ts`'s PATCH — `fields` is already
        `UserUpdate.model_dump(exclude_unset=True)` from the router."""
        user = await self.get_by_id_or_raise(user_id)
        if not fields:
            return user
        return await self._repository.update(user, fields)

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_by_id_or_raise(user_id)
        await self._repository.delete(user)

    async def upload_images(self, user_id: int, files: list[UploadFile]) -> list[Image]:
        """Port of `users/[id]/images/+server.ts`'s POST — bulk gallery upload. Does *not* set
        any of these as the user's avatar (that's the separate, still-unported `PATCH
        {image_id}` / `/users/{id}/image` singular-upload flow — see BACKEND_MIGRATION.md)."""
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
