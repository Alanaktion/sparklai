"""add group chat casts and message speakers

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-19 17:15:00.000000

"""

import sqlalchemy as sa
from alembic import op

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill(bind) -> None:
    """Give every existing session a one-character cast and a named speaker."""
    bind.execute(
        sa.text(
            'INSERT INTO session_characters (session_id, character_id, position) '
            'SELECT id, character_id, 0 FROM chat_sessions'
        )
    )
    bind.execute(
        sa.text(
            'UPDATE messages SET speaker_id = ('
            '  SELECT character_id FROM chat_sessions WHERE chat_sessions.id = messages.session_id'
            ') WHERE role = :role'
        ),
        {'role': 'assistant'},
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'session_characters',
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id', 'character_id'),
    )
    # SQLite cannot add a foreign key in place, so rebuild the table in batch mode.
    with op.batch_alter_table('messages') as batch:
        batch.add_column(sa.Column('speaker_id', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            'fk_messages_speaker_id_characters',
            'characters',
            ['speaker_id'],
            ['id'],
            ondelete='SET NULL',
        )

    _backfill(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('messages') as batch:
        batch.drop_constraint('fk_messages_speaker_id_characters', type_='foreignkey')
        batch.drop_column('speaker_id')
    op.drop_table('session_characters')
