"""add character tags and denormalized creator fields

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-19 14:32:29.965648

"""

import json
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _card_of(value: Any) -> dict:
    """Stored cards come back as a dict or as JSON text, depending on dialect."""
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _backfill(bind) -> None:
    """Fill the new columns and tag rows from the cards already on disk."""
    rows = bind.execute(sa.text('SELECT id, card_json FROM characters')).fetchall()
    seen: set[tuple[int, str]] = set()

    for row in rows:
        card = _card_of(row.card_json)
        data = card.get('data') if isinstance(card.get('data'), dict) else {}

        bind.execute(
            sa.text(
                'UPDATE characters SET creator = :creator, '
                'character_version = :version WHERE id = :id'
            ),
            {
                'creator': str(data.get('creator') or '')[:200],
                'version': str(data.get('character_version') or '')[:100],
                'id': row.id,
            },
        )

        for tag in data.get('tags') or []:
            if not isinstance(tag, str):
                continue
            normalized = tag.strip().lower()[:100]
            key = (row.id, normalized)
            if not normalized or key in seen:
                continue
            seen.add(key)
            bind.execute(
                sa.text(
                    'INSERT INTO character_tags (character_id, tag) VALUES (:id, :tag)'
                ),
                {'id': row.id, 'tag': normalized},
            )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('character_tags',
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('tag', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('character_id', 'tag')
    )
    op.create_index(op.f('ix_character_tags_tag'), 'character_tags', ['tag'], unique=False)
    # The empty server default lets these be added to a populated table.
    op.add_column('characters', sa.Column('creator', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False, server_default=''))
    op.add_column('characters', sa.Column('character_version', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False, server_default=''))
    op.create_index(op.f('ix_characters_creator'), 'characters', ['creator'], unique=False)

    _backfill(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_characters_creator'), table_name='characters')
    op.drop_column('characters', 'character_version')
    op.drop_column('characters', 'creator')
    op.drop_index(op.f('ix_character_tags_tag'), table_name='character_tags')
    op.drop_table('character_tags')
