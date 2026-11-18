"""MLBB akkaunt ulash: server va tekshirilganlik belgisi

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa
from alembic import op

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('ml_server', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('ml_verified', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'ml_verified')
    op.drop_column('users', 'ml_server')
