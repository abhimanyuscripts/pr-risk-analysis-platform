from cryptography.fernet import InvalidToken
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from auth.encryption import decrypt_token
from auth.jwt_handler import decode_access_token
from settings import allowed_writers


# Declares "Authorization: Bearer <token>" to FastAPI, which is what makes Swagger (/api/docs) show an
# Authorize button. auto_error=False keeps our own 401 message instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)


def _user_from_token(token: str, db: Session) -> User:
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
                     db: Session = Depends(get_db)) -> User:
    if credentials is None:  # no header, or a scheme other than Bearer
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return _user_from_token(credentials.credentials, db)


def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
                      db: Session = Depends(get_db)) -> User | None:
    """For pages anyone may read (the public demo). No token = a visitor (None). A token that is
    sent but expired or invalid is still a 401, so the app knows to forget it."""
    if credentials is None:
        return None
    return _user_from_token(credentials.credentials, db)


def require_writer(current_user: User = Depends(get_current_user)) -> User:
    """Only accounts listed in ALLOWED_WRITERS may change stored data (ingest, metrics, labels)."""
    if current_user.github_username.lower() not in allowed_writers():
        raise HTTPException(
            status_code=403,
            detail="This account can read but not change data. The site owner can add it to ALLOWED_WRITERS.",
        )
    return current_user


def get_github_token(current_user: User = Depends(get_current_user)) -> str:
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="No GitHub token stored for this user")

    try:
        return decrypt_token(current_user.github_access_token)
    except InvalidToken:  # TOKEN_ENCRYPTION_KEY was rotated after this token was stored
        raise HTTPException(status_code=401, detail="Stored GitHub token can't be decrypted - log in again via /api/auth/login")
