"""Per-user defaults used when assembling prompts."""

from sqlmodel import Field, SQLModel


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"

    # One settings row per user, so the foreign key doubles as the primary key.
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", primary_key=True)
    default_system_prompt: str = ""
    default_ujb: str = ""
    # Nullable by design; the foreign key to `providers.id` arrives with the
    # providers milestone (M4).
    default_provider_id: int | None = Field(default=None)


class UserSettingsUpdate(SQLModel):
    """Partial update payload; omitted fields are left unchanged."""

    default_system_prompt: str | None = None
    default_ujb: str | None = None
    default_provider_id: int | None = None


class UserSettingsPublic(SQLModel):
    user_id: int
    default_system_prompt: str
    default_ujb: str
    default_provider_id: int | None
