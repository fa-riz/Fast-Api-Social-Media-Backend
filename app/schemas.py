from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, conint


class Post(BaseModel):
    id: int | None = None
    title: str
    content: str
    published: bool = True
    user_id: int


class PostCreate(BaseModel):
    title: str
    content: str
    published: bool = True


class PostUpdate(BaseModel):
    """Phase 0 fix: no `id` / `user_id` in the body anymore. The row is looked
    up from the path param and ownership is checked against the authenticated
    user server-side -- a client can no longer edit someone else's post just
    by changing a field in the JSON body."""
    title: str | None = None
    content: str | None = None
    published: bool | None = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    role: str
    model_config = ConfigDict(from_attributes=True)


class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    published: bool
    created_at: datetime
    user_id: int
    user: UserResponse
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UpdateUser(BaseModel):
    id: int | None = None
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    """Phase 0: login now returns both tokens. `refresh_token` is opaque --
    it is not a JWT and carries no decodable payload."""
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    id: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str


class Vote(BaseModel):
    post_id: int
    dir: conint(ge=-1, le=1)  # 1 = upvote, -1 = remove/downvote


class PostOut(BaseModel):
    Posts: PostResponse
    vote_count: int

    model_config = ConfigDict(from_attributes=True)


# --- Phase 1: Comments --------------------------------------------------

class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


class CommentUpdate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: int
    content: str
    post_id: int
    user_id: int
    parent_id: int | None
    created_at: datetime
    is_deleted: bool
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


# --- Phase 2: Follows -----------------------------------------------------

class FollowResponse(BaseModel):
    follower_id: int
    followed_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowerUserOut(BaseModel):
    """A user shown in a followers/following list, with the follow edge's
    own created_at (when the follow happened) alongside their profile."""
    id: int
    email: EmailStr
    is_active: bool
    role: str
    followed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowStats(BaseModel):
    user_id: int
    followers_count: int
    following_count: int


# --- Phase 3: Feed ----------------------------------------------------------

class FeedItem(BaseModel):
    """One post as it appears in a feed page. Deliberately its own schema
    (rather than reusing PostOut) because a feed item also carries an
    optional `score` -- meaningless outside a ranked feed -- and needs a flat
    shape that's cheap to JSON-cache in Redis (see feed.py)."""
    id: int
    title: str
    content: str
    published: bool
    created_at: datetime
    user_id: int
    user: UserResponse
    vote_count: int
    score: float | None = None  # only set when sort="hot"

    model_config = ConfigDict(from_attributes=True)


class FeedPage(BaseModel):
    items: list[FeedItem]
    next_cursor: str | None = None  # pass this back as ?cursor= to get the next page; None = no more pages


# --- Phase 4: Media uploads --------------------------------------------------

class MediaUploadRequest(BaseModel):
    filename: str
    content_type: str
    media_type: str  # "image" | "video"


class MediaUploadResponse(BaseModel):
    """What the client needs to actually perform the upload, plus the object
    key it must echo back to POST /media once the upload succeeds."""
    upload_url: str
    object_key: str
    cdn_url: str
    expires_in: int


class MediaConfirm(BaseModel):
    object_key: str
    media_type: str
    post_id: int | None = None


class MediaResponse(BaseModel):
    id: int
    url: str
    media_type: str
    post_id: int | None
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Phase 5: Notifications ---------------------------------------------------

class NotificationResponse(BaseModel):
    id: int
    recipient_id: int
    actor_id: int
    actor: UserResponse
    type: str
    target_type: str
    target_id: int
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    unread_count: int


# --- Phase 6: Direct messaging -----------------------------------------------

class ConversationCreate(BaseModel):
    participant_ids: list[int]  # other users to include; the creator is added automatically


class ConversationParticipantOut(BaseModel):
    user_id: int
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: int
    created_at: datetime
    participants: list[ConversationParticipantOut]

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    created_at: datetime
    is_read: bool

    model_config = ConfigDict(from_attributes=True)


class MessagePage(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None = None


class WSMessageOut(BaseModel):
    """What gets pushed down the WebSocket to other participants when a new
    message is sent. Separate from MessageResponse only so the WS payload can
    carry an explicit `event` discriminator -- a real client might later push
    other event types (typing, read-receipts) down the same socket."""
    event: str = "message.created"
    message: MessageResponse
