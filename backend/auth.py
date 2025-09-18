# backend/auth.py
from datetime import datetime, timedelta
from typing import Optional
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import User, get_user_db

# --- Configuration ---
# MODIFIED: Read the secret key from an environment variable
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set for JWT. Please set it as an environment variable.")
ALGORITHM = "HS256"
# MODIFIED: Shorten Access Token lifetime
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes
# ADDED: Add a long lifetime for the Refresh Token
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# --- Pydantic Models for Token Data ---
class TokenData(BaseModel):
    username: Optional[str] = None

# --- Core Authentication Functions ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Default to the standard access token expiry if not provided
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(db: Session, username: str) -> Optional[User]:
    """
    Retrieves a user from the database by their username.
    """
    return db.query(User).filter(User.username == username).first()

# ADDED: A new helper function to decode a token and get the user
def get_user_from_token(token: str, db: Session) -> User:
    """
    Decodes a token, validates the username, and fetches the user from the user DB.
    This is a reusable version of the logic in get_current_user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_user_db)) -> User:
    """

    Dependency to get the current authenticated user from the Authorization header.
    """
    return get_user_from_token(token=token, db=db)

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    A simple dependency to check if the user is "active".
    """
    return current_user