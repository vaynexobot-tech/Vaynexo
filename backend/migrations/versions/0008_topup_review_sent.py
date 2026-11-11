"""topups.review_sent — avtomatik topilmagan to'lov haqida adminga bir marta eslatma

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('topups', sa.Column('review_sent', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('topups', 'review_sent')
