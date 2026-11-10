"""identifikatsiya, PIN, bildirishnomalar, saqlangan kartalar

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('kyc_status', sa.String(16), nullable=False, server_default='none'))
    op.add_column('users', sa.Column('kyc_note', sa.String(300), nullable=True))
    op.add_column('users', sa.Column('kyc_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('pin_hash', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('pin_ver', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('bio_hash', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('notify_chat', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('notify_tour', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index('ix_users_kyc_status', 'users', ['kyc_status'])
    op.add_column('tournaments', sa.Column('reminded', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'payment_cards',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('number_enc', sa.Text(), nullable=False),
        sa.Column('last4', sa.String(4), nullable=False),
        sa.Column('brand', sa.String(16), nullable=False),
        sa.Column('holder', sa.String(64), nullable=False),
        sa.Column('expiry', sa.String(5), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payment_cards_user_id', 'payment_cards', ['user_id'])
    op.create_index('ix_payment_cards_created_at', 'payment_cards', ['created_at'])


def downgrade() -> None:
    op.drop_table('payment_cards')
    op.drop_column('tournaments', 'reminded')
    op.drop_index('ix_users_kyc_status', 'users')
    for c in ('notify_tour', 'notify_chat', 'bio_hash', 'pin_ver', 'pin_hash', 'kyc_at', 'kyc_note', 'kyc_status'):
        op.drop_column('users', c)
