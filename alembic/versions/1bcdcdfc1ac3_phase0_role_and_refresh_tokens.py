"""phase 0: users.role column + refresh_tokens table

Revision ID: 1bcdcdfc1ac3
Revises: 20725d1142b1
Create Date: 2026-09-12 00:00:01.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1bcdcdfc1ac3'
down_revision = '20725d1142b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 'user' / 'mod' / 'admin' as a plain string, not a Postgres ENUM type --
    # see Phase 9 gotcha (enum-column migrations are painful to alter later;
    # a plain string with app-level validation is cheaper for a 3-value set
    # that may grow).
    op.add_column(
        'users',
        sa.Column('role', sa.String(), nullable=False, server_default='user'),
    )

    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False, unique=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_token_hash', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_column('users', 'role')
