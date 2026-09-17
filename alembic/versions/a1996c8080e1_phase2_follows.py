"""phase 2: follows table (follower/following graph)

Revision ID: a1996c8080e1
Revises: 08f8c721c27a
Create Date: 2026-09-12 00:00:03.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1996c8080e1'
down_revision = '08f8c721c27a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'follows',
        # Composite primary key -- (follower_id, followed_id) together are
        # unique by definition, so no extra unique index is needed on top.
        sa.Column('follower_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('followed_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.CheckConstraint('follower_id != followed_id', name='ck_follows_no_self_follow'),
    )
    # Composite PK already indexes (follower_id, followed_id) in that order,
    # which makes "followers/following of X" lookups on follower_id fast.
    # followed_id needs its own index for the reverse lookup ("who follows X").
    op.create_index('ix_follows_followed_id', 'follows', ['followed_id'])


def downgrade() -> None:
    op.drop_index('ix_follows_followed_id', table_name='follows')
    op.drop_table('follows')
