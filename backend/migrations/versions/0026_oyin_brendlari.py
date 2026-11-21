"""o'yin: har API'dagi brend nomi (bir o'yinda bir nechta provayder)

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-21 06:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('donate_games', sa.Column('brands', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    # mavjud bog'lanishlar: joriy provayder va uning brendi
    op.execute("UPDATE donate_games SET brands = jsonb_build_object(provider_id::text, brand_slug) "
               "WHERE provider_id IS NOT NULL AND brand_slug <> ''")


def downgrade() -> None:
    op.drop_column('donate_games', 'brands')
