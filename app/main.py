from fastapi import FastAPI, HTTPException, Response, status
from fastapi.params import Body, Depends
import psycopg2
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor 
import time
from .database import engine,get_db
from . import models



models.Base.metadata.create_all(bind=engine) # Create tables based on the models defined in models.py



class Post(BaseModel):
    id: int | None = None
    title: str
    content: str
    published: bool  = True
    
    


app = FastAPI()

@app.get("/")                                    # decoratr - '@'
async def root():                                #plain function that returns a JSON response with a message "Hello World"  
    return {"message": "Hello World ffdfd!!!!!!"}



@app.get("/posts")                                    # decoratr - '@'
async def get_posts(db: get_db = Depends(get_db)):
    # cursor.execute("SELECT * FROM posts")
    # data = cursor.fetchall()
    data = db.query(models.Posts).all()
    return data

@app.post("/posts")                                    # decoratr - '@'
async def create_post(payload: Post, db: get_db = Depends(get_db)):
    #  cursor.execute("SELECT COUNT(*) FROM posts ")
    # count = cursor.fetchone()['count']
    # new_post = payload.dict()
    # new_post["id"] = count + 1
    # cursor.execute("INSERT INTO posts (id, title, content, published) VALUES (%s, %s, %s, %s) RETURNING *", (new_post["id"], new_post["title"], new_post["content"], new_post["published"]))
    # created_post = cursor.fetchone()
    # conn.commit()
    
    new_post = models.Posts(**payload.dict())
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@app.get("/posts/latest")
def get_latest_post(db: get_db = Depends(get_db)):
    latest_post = db.query(models.Posts).order_by(models.Posts.id.desc()).first()
    if latest_post:
        return latest_post
    return {"error": "No posts available"}


@app.get("/posts/{post_id}")
def get_post(post_id: int, db: get_db = Depends(get_db)):
    post = db.query(models.Posts).filter(models.Posts.id == post_id).first()
    if post:
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")

@app.delete("/posts/{post_name}")
def delete_post(post_name: str, db: get_db = Depends(get_db)):
    post = db.query(models.Posts).filter(models.Posts.title == post_name).first()
    if post:
        db.delete(post)
        db.commit()
        return {"message": f"Post with title '{post_name}' deleted successfully with id {post.id}."}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with title '{post_name}' not found")

@app.put("/posts/{post_id}")
def update_post(post_id: int, payload: Post, db: get_db = Depends(get_db)):
    pd = payload.dict()
    if pd["id"] is None:
        pd["id"] = post_id
    if pd["id"] != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID in the payload does not match the path parameter")
    post = db.query(models.Posts).filter(models.Posts.id == post_id)
    # post = cursor.fetchone()
    if post:
        # cursor.execute("UPDATE posts SET title = %s, content = %s, published = %s WHERE id = %s", (pd["title"], pd["content"], pd["published"], post_id))
        # conn.commit()
        post.update(pd,synchronize_session=False)
        db.commit() 
        return {"message": f"Post with id {post_id} updated successfully."}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")