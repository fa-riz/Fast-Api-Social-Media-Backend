"""phase 6: conversations, conversation_participants, messages

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-20 00:00:06.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )

    op.create_table(
        'conversation_participants',
        # Composite PK -- same trick as Phase 2's Follows table: naturally
        # prevents adding the same user to a conversation twice.
        sa.Column('conversation_id', sa.Integer(),
                  sa.ForeignKey('conversations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('joined_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    # Reverse lookup: "which conversations is user X in" (the composite PK
    # above already indexes conversation_id-first lookups).
    op.create_index('ix_conversation_participants_user_id', 'conversation_participants', ['user_id'])

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.Integer(),
                  sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    # Matches the message-history query's ORDER BY conversation_id, created_at, id.
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at', 'id'])


def downgrade() -> None:
    op.drop_index('ix_messages_conversation_created', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_conversation_participants_user_id', table_name='conversation_participants')
    op.drop_table('conversation_participants')
    op.drop_table('conversations')
