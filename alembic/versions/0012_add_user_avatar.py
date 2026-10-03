"""add user profile image

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-03 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, Sequence[str], None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_settings', sa.Column('avatar_path', sa.String(), nullable=True))
    op.add_column('user_settings', sa.Column('avatar_original_path', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_settings', 'avatar_original_path')
    op.drop_column('user_settings', 'avatar_path')
