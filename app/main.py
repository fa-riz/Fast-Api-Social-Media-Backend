from fastapi import FastAPI

from .database import engine,get_db
from . import models
from .routers import posts,users,auth,votes
from pydantic_settings import BaseSettings
from .config import settings

models.Base.metadata.create_all(bind=engine) # Create tables based on the models defined in models.py

app = FastAPI()

app.include_router(posts.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(votes.router)  # Include the votes router to handle voting functionality

@app.get("/")                                    # decoratr - '@'
async def root():                                #plain function that returns a JSON response with a message "Hello World"  
    return {"message": "Hello World !!"}


