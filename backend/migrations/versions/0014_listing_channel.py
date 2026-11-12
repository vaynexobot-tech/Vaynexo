"""listings: e'lonlar kanalidagi post

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('channel_msg_id', sa.BigInteger(), nullable=True))
    op.add_column('listings', sa.Column('channel_state', sa.String(160), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'channel_state')
    op.drop_column('listings', 'channel_msg_id')
