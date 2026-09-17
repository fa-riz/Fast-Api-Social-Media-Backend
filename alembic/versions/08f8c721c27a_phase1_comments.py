"""phase 1: comments table (threaded via self-referential parent_id)

Revision ID: 08f8c721c27a
Revises: 1bcdcdfc1ac3
Create Date: 2026-09-12 00:00:02.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08f8c721c27a'
down_revision = '1bcdcdfc1ac3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'comments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('post_id', sa.Integer(),
                  sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        # Self-referential FK: nullable for top-level comments, points at
        # another comment's id for replies. No separate "depth" or "thread_id"
        # column -- depth is derived client-side by walking parent_id.
        sa.Column('parent_id', sa.Integer(),
                  sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index('ix_comments_post_id', 'comments', ['post_id'])
    op.create_index('ix_comments_parent_id', 'comments', ['parent_id'])


def downgrade() -> None:
    op.drop_index('ix_comments_parent_id', table_name='comments')
    op.drop_index('ix_comments_post_id', table_name='comments')
    op.drop_table('comments')
