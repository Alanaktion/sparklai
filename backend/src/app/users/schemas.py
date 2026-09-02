from app.core.schemas import BaseSchema
from app.posts.schemas import PostResponse


class UserCreate(BaseSchema):
    prompt: str | None = None


class UserResponse(BaseSchema):
    id: int
    name: str
    age: int
    pronouns: str
    bio: str | None = None
    location: dict | None = None
    occupation: str | None = None
    interests: list[str] | None = None
    personality_traits: str | None = None
    relationship_status: str | None = None
    writing_style: str | None = None
    backstory: str | None = None
    appearance: str | None = None
    image_id: int | None = None
    creator_id: int
    scenario: str | None = None
    first_mes: str | None = None
    is_active: bool


class UserUpdate(BaseSchema):
    """Matches the editable surface of the profile edit form (`edit/+page.svelte`), which submits
    the whole client-side user object on save — `id`/`creator_id` are deliberately not editable
    fields here, so they're silently ignored if present in the request body rather than letting a
    client reassign them."""

    name: str | None = None
    age: int | None = None
    pronouns: str | None = None
    bio: str | None = None
    location: dict | None = None
    occupation: str | None = None
    interests: list[str] | None = None
    personality_traits: str | None = None
    relationship_status: str | None = None
    writing_style: str | None = None
    backstory: str | None = None
    additional_prompt: str | None = None
    appearance: str | None = None
    memory: str | None = None
    image_id: int | None = None
    scenario: str | None = None
    first_mes: str | None = None
    is_active: bool | None = None


class ImageSummary(BaseSchema):
    id: int
    params: dict | None = None
    blur: bool


class RelationshipItem(BaseSchema):
    id: int
    name: str
    pronouns: str
    image_id: int | None = None
    relationship_type: str | None = None
    description: str | None = None


class UserProfileResponse(BaseSchema):
    """Bundle matching the old `users/[id]/+layout.server.ts` load — one call for the whole
    profile page shell (user, ownership, posts, gallery images, relationships)."""

    id: str
    user: UserResponse
    isOwner: bool
    posts: list[PostResponse]
    images: list[ImageSummary]
    relationships: list[RelationshipItem]


class PostGenerateRequest(BaseSchema):
    prompt: str | None = None


class ImageUploadResponse(BaseSchema):
    images: list[ImageSummary]
