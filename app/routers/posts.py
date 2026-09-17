from fastapi import HTTPException, status, APIRouter
from fastapi.params import Depends
from sqlalchemy import func
from typing import List

from app.database import get_db
from .. import models, schemas, oauth2


router = APIRouter(
    tags=["Posts"],
    responses={404: {"description": "Not found"}}
)


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
    new_post = models.Posts(**payload.dict(), user_id=current_user.id)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
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

    update_data = payload.dict(exclude_unset=True)
    post_query.update(update_data, synchronize_session=False)
    db.commit()
    return post_query.first()
