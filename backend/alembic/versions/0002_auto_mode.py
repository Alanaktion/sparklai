"""auto mode: creator/user automation settings + auto-generated tagging

Adds two new 1:1 settings tables (created lazily by the app, not backfilled here) plus an
`is_auto_generated` flag on `posts`/`comments` so the auto-mode activity log can tell bot-authored
content apart from human-triggered "generate" clicks.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "creator_auto_mode_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "creator_id",
            sa.Integer,
            sa.ForeignKey("creators.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("tick_interval_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("max_posts_per_tick", sa.Integer, nullable=False, server_default="2"),
        sa.Column("max_comments_per_tick", sa.Integer, nullable=False, server_default="5"),
        sa.Column("created_at", sa.Text, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "user_auto_mode_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("auto_post_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("auto_comment_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("post_frequency_per_day", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("comment_frequency_per_day", sa.Float, nullable=False, server_default="3.0"),
        sa.Column("created_at", sa.Text, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.add_column(
        "posts",
        sa.Column("is_auto_generated", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "comments",
        sa.Column("is_auto_generated", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("comments", "is_auto_generated")
    op.drop_column("posts", "is_auto_generated")
    op.drop_table("user_auto_mode_settings")
    op.drop_table("creator_auto_mode_settings")
