"""to'lov kartalari va «To'ladim» tekshiruvi

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('topups', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('topups', sa.Column('has_receipt', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('topups', sa.Column('reject_reason', sa.String(300), nullable=True))
    op.create_table(
        'p2p_cards',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('number', sa.String(32), nullable=False),
        sa.Column('holder', sa.String(64), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_p2p_cards_created_at', 'p2p_cards', ['created_at'])


def downgrade() -> None:
    op.drop_table('p2p_cards')
    for c in ('reject_reason', 'has_receipt', 'claimed_at'):
        op.drop_column('topups', c)
