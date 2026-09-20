"""add character packages and lorebook activation state

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-20 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Imported CHARX/PNG packages, kept so a V3 card's binary assets survive.
    op.add_column('characters', sa.Column('package_path', sa.String(), nullable=True))
    # Per-session lorebook match counts, for the V3 `@@*_activate_after_match`
    # decorators. The server default lets the column be added to a populated table.
    op.add_column(
        'chat_sessions',
        sa.Column('lorebook_state', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_sessions', 'lorebook_state')
    op.drop_column('characters', 'package_path')
