"""Do'konlar: shops, shop_sales, users.shop_id

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-26 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("shop_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_users_shop_id", "users", ["shop_id"])
    op.create_table(
        "shops",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("slug", sa.String(24), nullable=False, unique=True),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("tagline", sa.String(120), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "shop_sales",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("shop_id", sa.BigInteger(), sa.ForeignKey("shops.id"), nullable=False, index=True),
        sa.Column("buyer_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("commission", sa.BigInteger(), nullable=False),
        sa.Column("pct", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="paid"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("kind", "order_id", name="uq_shop_sale_order"),
    )


def downgrade() -> None:
    op.drop_table("shop_sales")
    op.drop_table("shops")
    op.drop_index("ix_users_shop_id", "users")
    op.drop_column("users", "shop_id")
