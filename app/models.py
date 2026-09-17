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
