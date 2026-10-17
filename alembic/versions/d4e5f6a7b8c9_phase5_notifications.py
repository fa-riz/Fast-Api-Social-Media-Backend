"""phase 5: notifications table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-20 00:00:05.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipient_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        # Plain strings, not Postgres ENUMs -- see Phase 0's `role` column and
        # the Phase 9 enum-migration gotcha. Values validated in application
        # code (app/routers/comments.py, follows.py, tasks.py).
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        # NOT a foreign key -- polymorphic target, same pattern as Phase 9's
        # Reports.target_id.
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('ix_notifications_recipient_id', 'notifications', ['recipient_id'])
    # Composite index matching the exact WHERE clause of GET /notifications/unread-count
    # (recipient_id = ? AND is_read = false) -- a single-column index on
    # recipient_id alone would still need to scan every one of that
    # recipient's rows to filter is_read.
    op.create_index(
        'ix_notifications_recipient_unread',
        'notifications',
        ['recipient_id', 'is_read'],
    )


def downgrade() -> None:
    op.drop_index('ix_notifications_recipient_unread', table_name='notifications')
    op.drop_index('ix_notifications_recipient_id', table_name='notifications')
    op.drop_table('notifications')
