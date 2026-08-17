from pydantic import BaseModel

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
    title: str | None = None
    content: str | None = None
    published: bool | None = None
    
class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    published: bool
    class Config:
        orm_mode = True
