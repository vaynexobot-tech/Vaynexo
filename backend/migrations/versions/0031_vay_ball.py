"""VAY ball: users.vay_xp (mavjud Arena ballidan boshlang'ich XP)

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-26 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("vay_xp", sa.BigInteger(), nullable=False, server_default="0"))
    # Hozirgacha ishlangan (musbat) Arena ballari ham hisobga olinadi
    op.execute("UPDATE users u SET vay_xp = COALESCE((SELECT SUM(amount) FROM points_ledger p WHERE p.user_id = u.id AND p.amount > 0), 0)")


def downgrade() -> None:
    op.drop_column("users", "vay_xp")
