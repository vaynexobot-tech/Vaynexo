"""Akkaunt savdo xavfsizligi: ushlab turish, muddat, strike, akkaunt xeshi

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-26 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("seller_strikes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("listings", sa.Column("account_key", sa.String(64), nullable=True))
    op.add_column("listings", sa.Column("account_enc", sa.Text(), nullable=True))
    op.create_index("ix_listings_account_key", "listings", ["account_key"])
    op.add_column("deals", sa.Column("deliver_by", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deals", sa.Column("deliver_warned", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("deals", sa.Column("hold_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deals", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_deals_deliver_by", "deals", ["deliver_by"])
    op.create_index("ix_deals_hold_until", "deals", ["hold_until"])
    # Mavjud ochiq bitimlar uchun muddat (eskilari to'xtab qolmasin)
    op.execute("UPDATE deals SET deliver_by = created_at + interval '12 hours' WHERE status = 'paid'")


def downgrade() -> None:
    op.drop_index("ix_deals_hold_until", "deals")
    op.drop_index("ix_deals_deliver_by", "deals")
    for c in ("confirmed_at", "hold_until", "deliver_warned", "deliver_by"):
        op.drop_column("deals", c)
    op.drop_index("ix_listings_account_key", "listings")
    op.drop_column("listings", "account_enc")
    op.drop_column("listings", "account_key")
    op.drop_column("users", "seller_strikes")
