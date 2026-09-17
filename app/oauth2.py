import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from fastapi.params import Depends
from fastapi import status, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app import schemas, database, models
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Phase 0 fix: secret key, algorithm and expiry all come from settings (env-backed),
# never hardcoded in source.
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days


def create_access_token(data: dict):
    cpy_data = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    cpy_data.update({"exp": expire})
    return jwt.encode(cpy_data, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("email")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception


def get_current_user(token: str = Depends(oauth2_scheme), db: database.get_db = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = verify_access_token(token, credentials_exception)

    user = db.query(models.Users).filter(models.Users.email == email).first()
    if user is None:
        raise credentials_exception

    return user


# --- Refresh tokens (Phase 0) -------------------------------------------------
# Refresh tokens are opaque random strings, not JWTs: the client can't decode
# anything useful out of them, and revocation is a DB row flip instead of
# waiting for a JWT to expire.

def generate_refresh_token() -> str:
    """Cryptographically random, URL-safe opaque token handed to the client."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """SHA-256 of the raw token. We only ever store/compare this hash -- a DB
    dump never yields a token an attacker can replay."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_and_store_refresh_token(db, user_id: int) -> str:
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = models.RefreshTokens(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(db_token)
    db.commit()
    return raw_token


def get_valid_refresh_token(db, raw_token: str):
    token_hash = hash_refresh_token(raw_token)
    db_token = db.query(models.RefreshTokens).filter(
        models.RefreshTokens.token_hash == token_hash
    ).first()

    if db_token is None:
        return None
    if db_token.revoked:
        return None

    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    return db_token


def revoke_refresh_token(db, db_token) -> None:
    db_token.revoked = True
    db.commit()


def revoke_all_user_refresh_tokens(db, user_id: int) -> None:
    """Used by Phase 9's ban endpoint: kill every live session for a user in
    one shot, not just block their next login."""
    db.query(models.RefreshTokens).filter(
        models.RefreshTokens.user_id == user_id,
        models.RefreshTokens.revoked == False,  # noqa: E712
    ).update({"revoked": True}, synchronize_session=False)
    db.commit()
