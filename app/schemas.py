
from datetime import datetime
import time

from pydantic import BaseModel, ConfigDict, EmailStr

class Post(BaseModel):
    id: int | None = None
    title: str
    content: str
    published: bool  = True
    

class PostCreate(BaseModel):
    title: str
    content: str
    published: bool = True 

class PostUpdate(BaseModel):
    id: int | None = None
    title: str | None = None
    content: str | None = None
    published: bool | None = None
    
class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    published: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    
    
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
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
    