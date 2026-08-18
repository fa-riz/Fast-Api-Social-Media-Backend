from fastapi import FastAPI, HTTPException, Response, status, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.params import  Depends
from app.database import get_db
from .. import models,schemas,utils,oauth2


router = APIRouter(
    tags=["Authentication"],
    responses={404: {"description": "Not found"}})



@router.post("/login", status_code=status.HTTP_200_OK, response_model=schemas.Token)
def user_login(payload: OAuth2PasswordRequestForm = Depends(), db: get_db = Depends(get_db)):
    if not payload.username or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username and password are required")

    user = db.query(models.Users).filter(models.Users.email == payload.username).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not utils.verify_password(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password")

    access_token = oauth2.create_access_token(data={"email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

