
from datetime import datetime
import time

from pydantic import BaseModel, ConfigDict, EmailStr, conint

class Post(BaseModel):
    id: int | None = None
    title: str
    content: str
    published: bool  = True
    user_id: int 
    

class PostCreate(BaseModel):
    title: str
    content: str
    published: bool = True 
    # Optional user_id field for creating a post

class PostUpdate(BaseModel):
    id: int | None = None
    title: str | None = None
    content: str | None = None
    published: bool | None = None
    user_id: int  # Optional user_id field for updating a post
    
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
    
class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    published: bool
    created_at: datetime
    user_id: int
    user : UserResponse  # Assuming you have a Users model with a 'posts' relationship defined
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
    
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
    
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: str | None = None
    
    
class Vote(BaseModel):
    post_id: int
    dir: conint(ge=-1, le=1)  # Assuming dir is an integer representing the direction of the vote (1 for upvote, -1 for downvote)
    