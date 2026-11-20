"""provayder SKU kodi uzunroq (FazerCards: «kategoriya|taklif»)

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-20 09:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('donate_packages', 'provider_sku', existing_type=sa.String(length=64), type_=sa.String(length=200), existing_nullable=False)


def downgrade() -> None:
    op.alter_column('donate_packages', 'provider_sku', existing_type=sa.String(length=200), type_=sa.String(length=64), existing_nullable=False)
