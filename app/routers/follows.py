from fastapi import HTTPException, status, APIRouter
from fastapi.params import Depends
from typing import List

from app.database import get_db
from .. import models, schemas, oauth2


router = APIRouter(
    tags=["Follows"],
    responses={404: {"description": "Not found"}}
)


def _get_user_or_404(db, user_id: int):
    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found")
    return user


@router.post("/users/{id}/follow", response_model=schemas.FollowResponse, status_code=status.HTTP_201_CREATED)
def follow_user(id: int, db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user)):
    if id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself")

    _get_user_or_404(db, id)

    existing = db.query(models.Follows).filter(
        models.Follows.follower_id == current_user.id,
        models.Follows.followed_id == id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already following this user")

    new_follow = models.Follows(follower_id=current_user.id, followed_id=id)
    db.add(new_follow)
    db.commit()
    db.refresh(new_follow)
    return new_follow


@router.delete("/users/{id}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(id: int, db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user)):
    follow = db.query(models.Follows).filter(
        models.Follows.follower_id == current_user.id,
        models.Follows.followed_id == id,
    ).first()

    if not follow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not following this user")

    db.delete(follow)
    db.commit()
    return None


@router.get("/users/{id}/followers", response_model=List[schemas.FollowerUserOut], status_code=status.HTTP_200_OK)
def get_followers(id: int, db: get_db = Depends(get_db), limit: int = 20, skip: int = 0):
    """Users who follow `id` -- i.e. rows where followed_id == id."""
    _get_user_or_404(db, id)

    rows = (
        db.query(models.Users, models.Follows.created_at.label("followed_at"))
        .join(models.Follows, models.Follows.follower_id == models.Users.id)
        .filter(models.Follows.followed_id == id)
        .order_by(models.Follows.created_at.desc())
        .limit(limit)
        .offset(skip)
        .all()
    )
    return [
        schemas.FollowerUserOut(
            id=user.id, email=user.email, is_active=user.is_active, role=user.role,
            followed_at=followed_at,
        )
        for user, followed_at in rows
    ]


@router.get("/users/{id}/following", response_model=List[schemas.FollowerUserOut], status_code=status.HTTP_200_OK)
def get_following(id: int, db: get_db = Depends(get_db), limit: int = 20, skip: int = 0):
    """Users that `id` follows -- i.e. rows where follower_id == id."""
    _get_user_or_404(db, id)

    rows = (
        db.query(models.Users, models.Follows.created_at.label("followed_at"))
        .join(models.Follows, models.Follows.followed_id == models.Users.id)
        .filter(models.Follows.follower_id == id)
        .order_by(models.Follows.created_at.desc())
        .limit(limit)
        .offset(skip)
        .all()
    )
    return [
        schemas.FollowerUserOut(
            id=user.id, email=user.email, is_active=user.is_active, role=user.role,
            followed_at=followed_at,
        )
        for user, followed_at in rows
    ]


@router.get("/users/{id}/follow-stats", response_model=schemas.FollowStats, status_code=status.HTTP_200_OK)
def get_follow_stats(id: int, db: get_db = Depends(get_db)):
    """Plain counts for now -- cache-friendly (see Phase 3 note in the docx):
    once Redis exists, this is a natural candidate for a short-TTL cache key
    like `follow-stats:{user_id}` instead of hitting Postgres on every call."""
    _get_user_or_404(db, id)

    followers_count = db.query(models.Follows).filter(models.Follows.followed_id == id).count()
    following_count = db.query(models.Follows).filter(models.Follows.follower_id == id).count()

    return schemas.FollowStats(
        user_id=id,
        followers_count=followers_count,
        following_count=following_count,
    )
