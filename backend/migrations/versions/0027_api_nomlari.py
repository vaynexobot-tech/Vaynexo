"""API nomlarida sayt nomi ko'rinmasin: «Yupay», «FazerCards» → «API 1», «API 2»

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-25 11:00:00.000000
"""
from alembic import op


revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE donate_providers p SET name = 'API ' || r.n
        FROM (SELECT id, row_number() OVER (ORDER BY id) AS n FROM donate_providers) r
        WHERE p.id = r.id AND (p.name ILIKE '%yupay%' OR p.name ILIKE '%fazer%' OR p.name ILIKE '%fzr%')
    """)


def downgrade() -> None:
    pass
