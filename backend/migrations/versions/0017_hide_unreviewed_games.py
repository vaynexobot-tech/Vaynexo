"""API'dan avtomatik ochilib qolgan o'yinlarni yashirish (admin ko'rib chiqib yoqadi)

Revision ID: 0017
Revises: 0016
"""
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None

SEEDED = ("ML", "MC", "pubg-mobile", "steam", "free-fire", "standoff-2", "delta-force", "genshin-impact", "roblox",
          "honor-of-kings", "blood-strike", "arena-breakout")


def upgrade() -> None:
    names = ", ".join(f"'{s}'" for s in SEEDED)
    op.execute(f"UPDATE donate_games SET is_active = false WHERE slug NOT IN ({names})")


def downgrade() -> None:
    pass
