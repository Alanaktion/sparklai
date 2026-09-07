"""SQLAlchemy models mirroring the pre-existing SQLite schema exactly.

Column names, nullability, defaults, and FK `ondelete` behavior all match the existing schema so
`local.db` can be adopted via `alembic stamp head` (see `app.db.migrate`) instead of being
recreated.

Timestamps are intentionally kept as `Text`, not `DateTime`: the schema stores them as plain
SQLite-formatted strings defaulting to `CURRENT_TIMESTAMP`, and mapping them to SQLAlchemy's
`DateTime` type risks a parsing mismatch against existing rows.
"""

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base

# Every `created_at`/`updated_at` column below is DB-side `DEFAULT CURRENT_TIMESTAMP` per the
# Alembic migration (alembic/versions/0001_baseline.py) — repeated here via `server_default` so
# SQLAlchemy's unit-of-work knows to actually omit the column from the INSERT and let SQLite fill
# it in. Without this, the ORM has no idea a server-side default exists, so any row created
# without explicitly passing e.g. `created_at=...` gets an explicit NULL written instead of the
# timestamp the DDL promises — which is exactly why freshly-created posts/comments/etc. were
# showing "Invalid Date" instead of missing rows just silently reusing the DDL default.
_NOW = text("CURRENT_TIMESTAMP")


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    pronouns: Mapped[str] = mapped_column(Text, nullable=False, default="they/them")
    bio: Mapped[str | None] = mapped_column(Text)
    location: Mapped[dict | None] = mapped_column(JSON)
    occupation: Mapped[str | None] = mapped_column(Text)
    interests: Mapped[list | None] = mapped_column(JSON)
    relationship_status: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)

    users: Mapped[list["User"]] = relationship(back_populates="creator")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    pronouns: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    location: Mapped[dict | None] = mapped_column(JSON)
    occupation: Mapped[str | None] = mapped_column(Text)
    interests: Mapped[list | None] = mapped_column(JSON)
    personality_traits: Mapped[str | None] = mapped_column(Text)
    relationship_status: Mapped[str | None] = mapped_column(Text)
    writing_style: Mapped[str | None] = mapped_column(Text)
    backstory: Mapped[str | None] = mapped_column(Text)
    additional_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    appearance: Mapped[str | None] = mapped_column(Text)
    memory: Mapped[str | None] = mapped_column(Text)
    # `users.image_id` <-> `images.user_id` is a genuine cycle (a user has a profile image, an
    # image belongs to a user); `use_alter` just tells SQLAlchemy it's a known one so it can order
    # DDL (and, if ever needed, DROP TABLE) without erroring.
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey("images.id", use_alter=True, name="fk_users_image_id")
    )
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("creators.id", ondelete="CASCADE"), nullable=False
    )
    scenario: Mapped[str | None] = mapped_column(Text)
    first_mes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    creator: Mapped["Creator"] = relationship(back_populates="users")
    image: Mapped["Image | None"] = relationship(foreign_keys=[image_id])
    posts: Mapped[list["Post"]] = relationship(back_populates="user")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON)
    type: Mapped[str] = mapped_column(Text, nullable=False, default="image/webp")
    data: Mapped[bytes] = mapped_column(nullable=False)
    blur: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[bytes] = mapped_column(nullable=False)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"))
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)

    user: Mapped["User"] = relationship(back_populates="posts")
    image: Mapped["Image | None"] = relationship(lazy="selectin")
    media: Mapped["Media | None"] = relationship(lazy="selectin")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)

    user: Mapped["User | None"] = relationship(lazy="selectin")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_en: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)

    image: Mapped["Image | None"] = relationship(lazy="selectin")


class ImageGenerationJob(Base):
    __tablename__ = "image_generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    target: Mapped[str] = mapped_column(Text, nullable=False)
    image_style: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    include_default_prompt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    set_as_user_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_job_id: Mapped[str | None] = mapped_column(Text)
    provider_metadata: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)
    updated_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)
    started_at: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)

    image: Mapped["Image | None"] = relationship(lazy="selectin")


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    related_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)

    related_user: Mapped["User"] = relationship(foreign_keys=[related_user_id], lazy="selectin")
