from fastapi import FastAPI, HTTPException, Response, status
from fastapi.params import Body
import psycopg2
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor 

class Post(BaseModel):
    id: int | None = None
    title: str
    content: str
    pubished: bool  = True
data = {"posts": [
        {"id": 1, "title": "First Post", "content": "This is the first post.", "published": True},
        {"id": 2, "title": "Second Post", "content": "This is the second post.", "published": True},
        {"id": 3, "title": "Third Post", "content": "This is the third post.", "published": True}
    ]}

try:
    conn = psycopg2.connect(host='localhost', database='insta', user='postgres', password='1234', cursor_factory=RealDictCursor)
    cursor = conn.cursor() #execute sql statements
    print("Database connection was successful")
except psycopg2.Error as e:
    print(f"Database connection error: {e}")

app = FastAPI()

@app.get("/")                                    # decoratr - '@'
async def root():                                #plain function that returns a JSON response with a message "Hello World"  
    return {"message": "Hello World ffdfd!!!!!!"}



@app.get("/posts")                                    # decoratr - '@'
async def get_posts():
    return data

@app.post("/posts")                                    # decoratr - '@'
async def create_post(payload: Post):
    new_post = payload.dict()
    new_post["id"] = payload.id if payload.id else len(data["posts"]) + 1
    data["posts"].append(new_post)
    return new_post
    
    

@app.get("/posts/latest")
def get_latest_post():
    if data["posts"]:
        latest_post = data["posts"][-1]
        return latest_post
    return {"error": "No posts available"}


@app.get("/posts/{post_id}")
def get_post(post_id: int,Response: Response):
    for post in data["posts"]:
        if post["id"] == post_id:
            return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")

@app.delete("/posts/{post_name}")
def delete_post(post_name: str):
    for post in data["posts"]:
        if post["title"] == post_name:
            del_post = post
            data["posts"].remove(post)
            return {"message": f"Post with title '{post_name}' deleted successfully with id {del_post['id']}."}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with title '{post_name}' not found")

@app.put("/posts/{post_id}")
def update_post(post_id: int, payload: Post):
    pd = payload.dict()
    if pd["id"] is None:
        pd["id"] = post_id
    if pd["id"] != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID in the payload does not match the path parameter")
    for post in data["posts"]:
        if post["id"] == post_id:
            post.update(pd)
            return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {post_id} not found")