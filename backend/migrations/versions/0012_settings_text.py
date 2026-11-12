"""app_settings.value → Text (shifrlangan Telegram sessiyasi uchun)

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('app_settings', 'value', type_=sa.Text(), existing_type=sa.String(500))


def downgrade() -> None:
    op.alter_column('app_settings', 'value', type_=sa.String(500), existing_type=sa.Text())
