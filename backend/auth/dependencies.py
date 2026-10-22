from cryptography.fernet import InvalidToken
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from auth.encryption import decrypt_token
from auth.jwt_handler import decode_access_token


def get_current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_github_token(current_user: User = Depends(get_current_user)) -> str:
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="No GitHub token stored for this user")

    try:
        return decrypt_token(current_user.github_access_token)
    except InvalidToken:  # TOKEN_ENCRYPTION_KEY was rotated after this token was stored
        raise HTTPException(status_code=401, detail="Stored GitHub token can't be decrypted - log in again via /auth/login")
