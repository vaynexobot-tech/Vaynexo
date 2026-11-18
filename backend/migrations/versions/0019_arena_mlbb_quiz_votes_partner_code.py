"""Arena: MLBB kartasi, viktorina, qahramon ovozi; jamoa e'loniga qahramonlar; hamkor promo-kodi

Revision ID: 0019
Revises: 0018
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('ml_nick', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('ml_lane', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('ml_rank', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('ml_heroes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('team_posts', sa.Column('heroes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('promo_codes', sa.Column('partner_id', sa.BigInteger(), nullable=True))
    op.create_index(op.f('ix_promo_codes_partner_id'), 'promo_codes', ['partner_id'], unique=False)
    op.create_table(
        'quiz_answers',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('day', sa.String(length=8), nullable=False),
        sa.Column('n', sa.Integer(), nullable=False),
        sa.Column('correct', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'day', 'n', name='uq_quiz_answer'),
    )
    op.create_index(op.f('ix_quiz_answers_user_id'), 'quiz_answers', ['user_id'], unique=False)
    op.create_index(op.f('ix_quiz_answers_created_at'), 'quiz_answers', ['created_at'], unique=False)
    op.create_table(
        'hero_votes',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('week', sa.String(length=8), nullable=False),
        sa.Column('hero_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'week', name='uq_hero_vote'),
    )
    op.create_index(op.f('ix_hero_votes_user_id'), 'hero_votes', ['user_id'], unique=False)
    op.create_index(op.f('ix_hero_votes_week'), 'hero_votes', ['week'], unique=False)
    op.create_index(op.f('ix_hero_votes_created_at'), 'hero_votes', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('hero_votes')
    op.drop_table('quiz_answers')
    op.drop_index(op.f('ix_promo_codes_partner_id'), table_name='promo_codes')
    op.drop_column('promo_codes', 'partner_id')
    op.drop_column('team_posts', 'heroes')
    for c in ('ml_heroes', 'ml_rank', 'ml_lane', 'ml_nick'):
        op.drop_column('users', c)
