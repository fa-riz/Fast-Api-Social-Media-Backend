from fastapi import FastAPI, HTTPException, Response, status, APIRouter
from fastapi.params import  Depends
from app.database import get_db
from .. import models,schemas,oauth2
from sqlalchemy import func 
from typing import List
import app



router = APIRouter(
    tags=["Posts"],
    responses={404: {"description": "Not found"}}
)


@router.get("/posts",response_model=List[schemas.PostOut], status_code=status.HTTP_200_OK)                                    # decoratr - '@'
async def get_posts(db: get_db = Depends(get_db),current_user: str = Depends(oauth2.get_current_user), limit: int = 10, skip: int = 0, search: str = ""):
     
    # cursor.execute("SELECT * FROM posts")
    # data = cursor.fetchall()
    data = db.query(models.Posts, func.count(models.Votes.user_id).label("vote_count")).join(models.Votes, models.Posts.id == models.Votes.post_id).filter(models.Votes.user_id == current_user.id).group_by(models.Posts.id).filter(models.Posts.title.contains(search)).limit(limit).offset(skip).all()
    
    return data

@router.post("/posts", response_model=schemas.PostResponse, status_code=status.HTTP_201_CREATED)                                    # decoratr - '@'
async def create_post(payload: schemas.PostCreate, db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user)):
    print("User creating post:", current_user)
   
    new_post = models.Posts(**payload.dict(), user_id=current_user.id)  # Assuming current_user is a user object with an 'id' attribute
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/posts/latest", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def get_latest_post(db: get_db = Depends(get_db)):
    latest_post = db.query(models.Posts).order_by(models.Posts.id.desc()).first()
    if latest_post:
        return latest_post
    return {"error": "No posts available"}


@router.get("/posts/{post_id}", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def get_post(post_id: int, db: get_db = Depends(get_db)):
    post = db.query(models.Posts).filter(models.Posts.id == post_id).first()
    if post:
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")

@router.delete("/posts/{id}", response_model=schemas.PostResponse, status_code = status.HTTP_200_OK)
def delete_post(id: int, db: get_db = Depends(get_db), current_user: str = Depends(oauth2.get_current_user)):
    post = db.query(models.Posts).filter(models.Posts.id == id).first()
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this post")

    if post:
        db.delete(post)
        db.commit()
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {id} not found")

@router.put("/posts/{post_id}", response_model=schemas.PostResponse, status_code=status.HTTP_200_OK)
def update_post(post_id: int, payload: schemas.PostUpdate, db: get_db = Depends(get_db)):
    pd = payload.dict()
    if pd["id"] is None:
        pd["id"] = post_id
    if pd["id"] != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID in the payload does not match the path parameter")
    post = db.query(models.Posts).filter(models.Posts.id == post_id)
    # post = cursor.fetchone()
    if post.first():
        # cursor.execute("UPDATE posts SET title = %s, content = %s, published = %s WHERE id = %s", (pd["title"], pd["content"], pd["published"], post_id))
        # conn.commit()
        post.update(pd,synchronize_session=False)
        db.commit() 
        return post.first()
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")

