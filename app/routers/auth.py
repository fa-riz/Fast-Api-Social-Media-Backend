from fastapi import HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.params import Depends

from app.database import get_db
from .. import models, schemas, utils, oauth2


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
    # Phase 0: also mint + store a refresh token so the client doesn't have to
    # re-login every time the short-lived access token expires.
    refresh_token = oauth2.create_and_store_refresh_token(db, user_id=user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login/refresh", status_code=status.HTTP_200_OK, response_model=schemas.AccessTokenResponse)
def refresh_access_token(payload: schemas.RefreshRequest, db: get_db = Depends(get_db)):
    """Phase 0: trade a valid, unexpired, unrevoked refresh token for a new
    access token. Does NOT rotate the refresh token itself (see docx notes on
    rotation as a future hardening step)."""
    db_token = oauth2.get_valid_refresh_token(db, payload.refresh_token)

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid, expired, or revoked",
        )

    user = db.query(models.Users).filter(models.Users.id == db_token.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    access_token = oauth2.create_access_token(data={"email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
