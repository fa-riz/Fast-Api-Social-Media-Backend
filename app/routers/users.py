from fastapi import FastAPI, HTTPException, Response, status, APIRouter
from fastapi.params import  Depends
from app.database import get_db
from .. import models,schemas,utils
import app



router = APIRouter(
    tags=["Users"],
    responses={404: {"description": "Not found"}}
    
)


@router.post("/users",response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate,db: get_db = Depends(get_db)):
    print("Payload received:", payload)
    payload.password = utils.hash_password(payload.password)  # Hash the password before storing it
    p = payload.dict()
    p["id"] = None  # Set id to None to let the database handle auto-increment
    new_user = models.Users(**p)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users",response_model=list[schemas.UserResponse], status_code=status.HTTP_200_OK)
def get_users(db: get_db = Depends(get_db)):
    data = db.query(models.Users).all()
    return data

@router.get("/users/{user_id}", response_model=schemas.UserResponse, status_code=status.HTTP_200_OK)
def get_user(user_id: int, db: get_db = Depends(get_db)):
    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found")

@router.put("/users/{user_id}", response_model=schemas.UserResponse, status_code=status.HTTP_200_OK)
def update_user(user_id: int, payload: schemas.UpdateUser, db: get_db = Depends(get_db)):
    pd = payload.dict()
    if pd["id"] is None:
        pd["id"] = user_id
    if pd["id"] != user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID in the payload does not match the path parameter")
    user = db.query(models.Users).filter(models.Users.id == user_id)
    if user.first():
        user.update(pd,synchronize_session=False)
        db.commit() 
        return user.first()
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found")

@router.delete("/users/{user_email}", response_model=schemas.UserResponse, status_code = status.HTTP_200_OK)
def delete_user(user_email: str, db: get_db = Depends(get_db)):
    user = db.query(models.Users).filter(models.Users.email == user_email).first()
    if user:
        db.delete(user)
        db.commit()
        return {"message": f"User with email '{user_email}' deleted successfully with id {user.id}."}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with email '{user_email}' not found")