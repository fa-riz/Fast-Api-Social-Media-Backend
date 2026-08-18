from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.params import Depends
from fastapi import   status, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

#secret key
SECRET_KEY = "09d25e094faa6ca2556cavav1241818166b7fsvsvsgsbsbbsbsbsbcxs"

#algorithm
ALGORITHM = "HS256"

#salt
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: dict):
    cpy_data = data.copy()
    
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
    
def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = verify_access_token(token, credentials_exception)
    return email
