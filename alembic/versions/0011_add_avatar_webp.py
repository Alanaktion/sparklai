"""add character avatar webp variant

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-20 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # An optimized WebP copy of the avatar, served to the UI so page loads do
    # not fetch the (potentially large) original PNG/JPG.
    op.add_column('characters', sa.Column('avatar_webp_path', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('characters', 'avatar_webp_path')
