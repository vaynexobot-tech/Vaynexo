"""donate_games: admin yuklagan rasm (bazada)

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('donate_games', sa.Column('image', sa.LargeBinary(), nullable=True))
    op.add_column('donate_games', sa.Column('image_ver', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('donate_games', 'image_ver')
    op.drop_column('donate_games', 'image')
