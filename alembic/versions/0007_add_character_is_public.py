"""add characters.is_public

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-19 16:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The false server default lets the column be added to a populated table.
    op.add_column(
        'characters',
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f('ix_characters_is_public'), 'characters', ['is_public'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_characters_is_public'), table_name='characters')
    op.drop_column('characters', 'is_public')
