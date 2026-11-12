"""topups: biriktirilgan karta (summa + karta bo'yicha moslash)

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('topups', sa.Column('card_number', sa.String(32), nullable=True))
    op.add_column('topups', sa.Column('card_holder', sa.String(64), nullable=True))
    op.add_column('topups', sa.Column('card_last4', sa.String(4), nullable=True))
    op.create_index('ix_topups_card_last4', 'topups', ['card_last4'])


def downgrade() -> None:
    op.drop_index('ix_topups_card_last4', 'topups')
    for c in ('card_last4', 'card_holder', 'card_number'):
        op.drop_column('topups', c)
