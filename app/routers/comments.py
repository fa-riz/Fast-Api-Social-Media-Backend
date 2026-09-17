from fastapi import HTTPException, status, APIRouter
from fastapi.params import Depends
from typing import List

from app.database import get_db
from .. import models, schemas, oauth2


router = APIRouter(
    tags=["Comments"],
    responses={404: {"description": "Not found"}}
)


def _get_post_or_404(db, post_id: int):
    post = db.query(models.Posts).filter(models.Posts.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")
    return post


def _get_comment_or_404(db, comment_id: int):
    comment = db.query(models.Comments).filter(models.Comments.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Comment with id {comment_id} not found")
    return comment


@router.post("/posts/{post_id}/comments", response_model=schemas.CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(post_id: int, payload: schemas.CommentCreate, db: get_db = Depends(get_db),
                    current_user: str = Depends(oauth2.get_current_user)):
    _get_post_or_404(db, post_id)

    if payload.parent_id is not None:
        parent = db.query(models.Comments).filter(models.Comments.id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                 detail=f"Parent comment with id {payload.parent_id} not found")
        if parent.post_id != post_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                 detail="Parent comment does not belong to this post")

    new_comment = models.Comments(
        content=payload.content,
        post_id=post_id,
        user_id=current_user.id,
        parent_id=payload.parent_id,
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


@router.get("/posts/{post_id}/comments", response_model=List[schemas.CommentResponse], status_code=status.HTTP_200_OK)
def get_comments(post_id: int, db: get_db = Depends(get_db)):
    """Returns a flat list (id, parent_id, created_at) -- the client builds the
    reply tree itself. See the build-plan gotcha: recursive tree-fetch queries
    don't scale, flat-list + client nesting does."""
    _get_post_or_404(db, post_id)

    comments = (
        db.query(models.Comments)
        .filter(models.Comments.post_id == post_id)
        .order_by(models.Comments.created_at.asc())
        .all()
    )
    return comments


@router.put("/comments/{id}", response_model=schemas.CommentResponse, status_code=status.HTTP_200_OK)
def update_comment(id: int, payload: schemas.CommentUpdate, db: get_db = Depends(get_db),
                    current_user: str = Depends(oauth2.get_current_user)):
    comment_query = db.query(models.Comments).filter(models.Comments.id == id)
    comment = comment_query.first()

    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Comment with id {id} not found")

    if comment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this comment")

    if comment.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a deleted comment")

    comment_query.update({"content": payload.content}, synchronize_session=False)
    db.commit()
    return comment_query.first()


@router.delete("/comments/{id}", response_model=schemas.CommentResponse, status_code=status.HTTP_200_OK)
def delete_comment(id: int, db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user)):
    """Soft delete: flip `is_deleted` and blank the content, keep the row.
    Replies further down the thread still resolve their parent_id -- a hard
    delete would either orphan them or force a cascade that wipes the whole
    subtree."""
    comment_query = db.query(models.Comments).filter(models.Comments.id == id)
    comment = comment_query.first()

    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Comment with id {id} not found")

    if comment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this comment")

    comment_query.update({"is_deleted": True, "content": ""}, synchronize_session=False)
    db.commit()
    return comment_query.first()
