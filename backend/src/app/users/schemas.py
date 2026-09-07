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
    """One directional relationship row, from the owning user's (`{user_id}` in the URL)
    perspective, with the related user's display info denormalized in. Used both in
    `UserProfileResponse.relationships` and as the response model for the relationship
    create/update endpoints below.

    `relationship_id` is the `Relationship` row's own PK (for targeting PATCH/DELETE); `id` is the
    *related* user's id (for linking to their profile) — kept as `id` rather than renamed, since
    the frontend already keys off it for that link."""

    relationship_id: int
    id: int
    name: str
    pronouns: str
    image_id: int | None = None
    relationship_type: str | None = None
    description: str | None = None


class RelationshipCreate(BaseSchema):
    """Creates a relationship from the owning user (`{user_id}` in the URL) to
    `related_user_id` — both must belong to the same creator's roster. `mutual` (default `True`)
    also creates/updates the reverse row, so both characters treat each other as connected.

    The reverse row's label defaults to mirroring `relationship_type`/`description` exactly —
    right for symmetric relationships ("best friend", "sibling"). For asymmetric ones (a "child"
    on one side is a "parent" on the other), set `reverse_relationship_type`/`reverse_description`
    to describe the relationship from the *other* character's perspective instead."""

    related_user_id: int
    relationship_type: str | None = None
    description: str | None = None
    mutual: bool = True
    reverse_relationship_type: str | None = None
    reverse_description: str | None = None


class RelationshipUpdate(BaseSchema):
    relationship_type: str | None = None
    description: str | None = None


class UserProfileResponse(BaseSchema):
    """One call for the whole profile page shell (user, ownership, posts, gallery images,
    relationships)."""

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


class AvatarUploadResponse(BaseSchema):
    image: ImageSummary


class DreamResponse(BaseSchema):
    memory: str
