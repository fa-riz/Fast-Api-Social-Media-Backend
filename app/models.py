from sqlalchemy import TIMESTAMP, Column, ForeignKey, Integer, String, text, Boolean, CheckConstraint
from .database import Base
from sqlalchemy.orm import relationship


class Users(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    is_active = Column(Boolean, server_default=text('true'), nullable=False)
    # Phase 0: role-based access control. Plain string on purpose (not an enum) so
    # adding a role later is a data change, not a schema migration.
    role = Column(String, nullable=False, server_default='user')  # 'user' | 'mod' | 'admin'


class Posts(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default=text('true'))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users")


class Votes(Base):
    __tablename__ = 'votes'

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)


class RefreshTokens(Base):
    """Phase 0: opaque refresh tokens. We store only a SHA-256 hash of the token
    (never the raw token) so a DB leak doesn't hand out working sessions."""
    __tablename__ = 'refresh_tokens'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, server_default=text('false'))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

    user = relationship("Users")


class Comments(Base):
    """Phase 1: flat storage, tree built client-side via parent_id.
    is_deleted is a soft-delete flag: on delete we blank the content and keep
    the row so replies further down the thread don't lose their parent."""
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))

    user = relationship("Users")
    post = relationship("Posts")
    # Self-referential FK for replies. We don't eager-load a `replies` tree here on
    # purpose (see gotcha in the build plan) -- the API returns a flat list and the
    # client nests by parent_id.
    parent = relationship("Comments", remote_side=[id])


class Follows(Base):
    """Phase 2: composite primary key (follower_id, followed_id) naturally
    prevents duplicate follow rows -- no separate unique index needed on top
    of the PK. The CHECK constraint blocks a user from following themself at
    the database level, not just in application code."""
    __tablename__ = 'follows'

    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    followed_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

    __table_args__ = (
        CheckConstraint('follower_id != followed_id', name='ck_follows_no_self_follow'),
    )

    follower = relationship("Users", foreign_keys=[follower_id])
    followed = relationship("Users", foreign_keys=[followed_id])


# Phase 3 (feed generation) introduces no new tables -- it reads Posts,
# Votes and Follows that already exist, and caches computed results in
# Redis rather than Postgres. See app/routers/feed.py.


class Media(Base):
    """Phase 4: one row per uploaded file. We never store the file bytes in
    Postgres -- only the CDN-facing URL and the S3 object key needed to
    manage/delete the underlying object. `post_id` is nullable because an
    upload is confirmed (this row is created) slightly before the client has
    necessarily attached it to a post."""
    __tablename__ = 'media'

    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)               # CDN url, never the raw bucket url
    media_type = Column(String, nullable=False)         # 'image' | 'video'
    object_key = Column(String, nullable=False, unique=True)  # S3/R2 key, e.g. uploads/7/ab12-photo.jpg
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

    user = relationship("Users")
    post = relationship("Posts")


class Notifications(Base):
    """Phase 5: `type` and `target_type` are plain strings, not Postgres
    ENUMs -- same reasoning as Users.role (see Phase 0 note above and the
    Phase 9 gotcha): a 3-8 value set that may grow, where adding a value to
    a plain string column is a data change, not a migration.

    `target_id` is intentionally NOT a foreign key -- it's polymorphic (a
    comment id, a follow's follower_id, a post id, depending on `type`), so
    it's validated in application code instead. Same pattern the build plan
    uses for Reports.target_id in Phase 9."""
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)          # 'comment' | 'reply' | 'follow'
    target_type = Column(String, nullable=False)   # 'post' | 'comment' | 'user'
    target_id = Column(Integer, nullable=False)
    is_read = Column(Boolean, nullable=False, server_default=text('false'))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

    recipient = relationship("Users", foreign_keys=[recipient_id])
    actor = relationship("Users", foreign_keys=[actor_id])


class Conversations(Base):
    """Phase 6. Deliberately just an id + timestamp -- who's *in* the
    conversation lives in ConversationParticipants, not here. That's what
    makes group DMs possible later without a schema change (see build-plan
    gotcha: "participants join table, not a flat sender/recipient pair")."""
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)


class ConversationParticipants(Base):
    """Join table between Conversations and Users. Composite PK, same trick
    as Follows in Phase 2 -- naturally prevents adding the same user to a
    conversation twice, no extra unique index needed."""
    __tablename__ = 'conversation_participants'

    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)

    user = relationship("Users")


class Messages(Base):
    """Phase 6. `is_read` here is a simple per-message flag (good enough for
    a 1:1 or small-group DM). A larger system would instead track a
    per-participant "last read message id" on ConversationParticipants --
    see the docx for why that scales better with many participants."""
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
    is_read = Column(Boolean, nullable=False, server_default=text('false'))

    sender = relationship("Users")
    conversation = relationship("Conversations")
