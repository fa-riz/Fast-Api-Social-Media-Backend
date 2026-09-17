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
