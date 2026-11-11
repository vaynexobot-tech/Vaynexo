"""users.wallet_id — har bir foydalanuvchiga hamyon ID

Revision ID: 0009
Revises: 0008
"""
import random

from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('wallet_id', sa.String(12), nullable=True))
    op.create_unique_constraint('uq_users_wallet_id', 'users', ['wallet_id'])
    conn = op.get_bind()
    ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM users WHERE wallet_id IS NULL"))]
    used: set[str] = set()
    for uid in ids:
        while True:
            w = str(random.SystemRandom().randint(10_000_000, 99_999_999))
            if w not in used:
                used.add(w)
                break
        conn.execute(sa.text("UPDATE users SET wallet_id = :w WHERE id = :id"), {"w": w, "id": uid})


def downgrade() -> None:
    op.drop_constraint('uq_users_wallet_id', 'users', type_='unique')
    op.drop_column('users', 'wallet_id')
