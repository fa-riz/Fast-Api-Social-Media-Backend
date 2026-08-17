from fastapi import FastAPI, HTTPException, Response, status
import time
from .database import engine,get_db
from . import models
from .routers import posts,users




models.Base.metadata.create_all(bind=engine) # Create tables based on the models defined in models.py





app = FastAPI()

app.include_router(posts.router)
app.include_router(users.router)

@app.get("/")                                    # decoratr - '@'
async def root():                                #plain function that returns a JSON response with a message "Hello World"  
    return {"message": "Hello World ffdfd!!!!!!"}


