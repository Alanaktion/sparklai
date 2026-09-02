from app.core.schemas import BaseSchema


class CreatorCreate(BaseSchema):
    name: str
    pin: str
    pronouns: str = "they/them"


class CreatorLogin(BaseSchema):
    pin: str


class CreatorResponse(BaseSchema):
    id: int
    name: str
    age: int
    pronouns: str
    bio: str | None = None
    location: dict | None = None
    occupation: str | None = None
    interests: list[str] | None = None
    relationship_status: str | None = None
    is_active: bool
    created_at: str | None = None


class CreatorUpdate(BaseSchema):
    """Partial update for the settings page. Unlike the old SvelteKit form action (which always
    replaced bio/occupation/interests/relationship_status wholesale, defaulting to null when the
    form field was blank), this only touches fields the client actually sends."""

    name: str | None = None
    age: int | None = None
    pronouns: str | None = None
    bio: str | None = None
    location: dict | None = None
    occupation: str | None = None
    interests: list[str] | None = None
    relationship_status: str | None = None
