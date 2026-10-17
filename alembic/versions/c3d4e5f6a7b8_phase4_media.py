"""phase 4: media table (S3/R2 uploads)

Revision ID: c3d4e5f6a7b8
Revises: a1996c8080e1
Create Date: 2026-09-20 00:00:04.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'a1996c8080e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'media',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('media_type', sa.String(), nullable=False),
        # unique: object_key doubles as our idempotency key for the
        # confirm-upload endpoint (POST /media rejects a key it's already seen).
        sa.Column('object_key', sa.String(), nullable=False, unique=True),
        sa.Column('post_id', sa.Integer(),
                  sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_media_post_id', 'media', ['post_id'])
    op.create_index('ix_media_user_id', 'media', ['user_id'])
    op.create_index('ix_media_object_key', 'media', ['object_key'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_media_object_key', table_name='media')
    op.drop_index('ix_media_user_id', table_name='media')
    op.drop_index('ix_media_post_id', table_name='media')
    op.drop_table('media')
