from fastapi import HTTPException, status, APIRouter
from fastapi.params import Depends
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from .. import models, schemas, oauth2
from ..tasks import notify_followers_of_post_task


router = APIRouter(
    tags=["Posts"],
    responses={404: {"description": "Not found"}}
)


def _load_attachable_media(db, media_ids, user_id, post_id=None):
    """Fetch the Media rows for `media_ids`, rejecting ids that don't exist,
    belong to someone else, or are attached to a post other than `post_id`."""
    media_ids = set(media_ids)
    if not media_ids:
        return []
    media = db.query(models.Media).filter(models.Media.id.in_(media_ids)).all()
    missing = media_ids - {m.id for m in media}
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Media not found: {sorted(missing)}")
    if any(m.user_id != user_id for m in media):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only attach your own media")
    if any(m.post_id is not None and m.post_id != post_id for m in media):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Media is already attached to a post")
    return media


@router.get("/posts", response_model=List[schemas.PostOut], status_code=status.HTTP_200_OK)
async def get_posts(db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user),
                     limit: int = 10, skip: int = 0, search: str = ""):
    # Phase 0 fix: LEFT OUTER JOIN so posts with zero votes still show up
    # (an INNER JOIN silently dropped them). Also dropped the old
    # `Votes.user_id == current_user.id` filter that was copy-pasted from the
    # /votes endpoint -- it accidentally restricted the whole feed to posts
    # *you* had voted on, instead of counting all votes on each post.
    data = (
        db.query(models.Posts, func.count(models.Votes.post_id).label("vote_count"))
        .options(selectinload(models.Posts.media))
        .outerjoin(models.Votes, models.Posts.id == models.Votes.post_id)
        .filter(models.Posts.title.contains(search))
        .group_by(models.Posts.id)
        .order_by(models.Posts.created_at.desc())
        .limit(limit)
        .offset(skip)
        .all()
    )

    return data


@router.post("/posts", response_model=schemas.PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(payload: schemas.PostCreate, db: get_db = Depends(get_db),
                       current_user: str = Depends(oauth2.get_current_user)):
    media = _load_attachable_media(db, payload.media_ids, current_user.id)

    new_post = models.Posts(**payload.dict(exclude={"media_ids"}), user_id=current_user.id)
    new_post.media = media
    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    # Phase 5: the per-follower fan-out happens in the worker, not here.
    if new_post.published:
        notify_followers_of_post_task.delay(author_id=current_user.id, post_id=new_post.id)
    return new_post


@router.get("/posts/latest", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def get_latest_post(db: get_db = Depends(get_db)):
    latest_post = db.query(models.Posts).order_by(models.Posts.id.desc()).first()
    if latest_post:
        return latest_post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No posts available")


@router.get("/posts/{post_id}", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def get_post(post_id: int, db: get_db = Depends(get_db)):
    post = db.query(models.Posts).filter(models.Posts.id == post_id).first()
    if post:
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")


@router.delete("/posts/{id}", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def delete_post(id: int, db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user)):
    post = db.query(models.Posts).filter(models.Posts.id == id).first()

    # Phase 0 fix: null-check BEFORE the ownership check. The old code did
    # `post.user_id` on a possibly-None `post`, which threw an unhandled
    # AttributeError -> FastAPI turned that into a raw 500 instead of a 404.
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {id} not found")

    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this post")

    db.delete(post)
    db.commit()
    return post


@router.put("/posts/{post_id}", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def update_post(post_id: int, payload: schemas.PostUpdate, db: get_db = Depends(get_db),
                 current_user: str = Depends(oauth2.get_current_user)):
    post_query = db.query(models.Posts).filter(models.Posts.id == post_id)
    post = post_query.first()

    # Phase 0 fix: null-check before ownership check -> clean 404 instead of 500.
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")

    # Phase 0 fix: ownership is checked against the authenticated user, not a
    # `user_id` the client could put in the request body. The `id`/`user_id`
    # fields were also removed from PostUpdate for the same reason -- there is
    # nothing left in the body a client could use to reassign the post.
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this post")

    update_data = payload.dict(exclude_unset=True, exclude={"media_ids"})
    if payload.media_ids is not None:
        # Media dropped from the list is detached (post_id -> NULL), not
        # deleted, so the upload can still be attached to another post.
        post.media = _load_attachable_media(db, payload.media_ids, current_user.id, post_id=post.id)
    if update_data:
        post_query.update(update_data, synchronize_session=False)
    db.commit()
    return post_query.first()
