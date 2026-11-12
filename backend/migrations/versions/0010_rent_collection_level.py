"""rent_listings.collection_level

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('rent_listings', sa.Column('collection_level', sa.String(32), server_default='', nullable=False))


def downgrade() -> None:
    op.drop_column('rent_listings', 'collection_level')
