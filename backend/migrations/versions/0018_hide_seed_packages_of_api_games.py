"""API'ga ulangan o'yinlarda boshlang'ich (seed) qo'lda paketlarni o'chirish — haqiqiy API paketlari bor

Revision ID: 0018
Revises: 0017
"""
from alembic import op

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE donate_packages SET is_active = false
        WHERE source = 'manual' AND (provider_sku LIKE 'ML\\_%' OR provider_sku LIKE 'MC\\_%')
          AND game IN (SELECT slug FROM donate_games WHERE provider_id IS NOT NULL)
          AND game IN ('ML', 'MC') AND id <= 17
    """)


def downgrade() -> None:
    pass
