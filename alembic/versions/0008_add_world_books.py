"""add world books and the per-session world book toggle

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-19 16:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_settings', sa.Column('world_book', sa.JSON(), nullable=True))
    # The true server default lets the column be added to a populated table.
    op.add_column(
        'chat_sessions',
        sa.Column('use_world_book', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_sessions', 'use_world_book')
    op.drop_column('user_settings', 'world_book')
