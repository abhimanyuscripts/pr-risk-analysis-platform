import os
import secrets
from urllib.parse import urlencode

import httpx
from auth.encryption import encrypt_token
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from auth.jwt_handler import create_access_token
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
# Public repos need no extra scope; set "read:user repo" only if private repos must be analysed
OAUTH_SCOPE = os.getenv("GITHUB_OAUTH_SCOPE", "read:user")
STATE_MAX_AGE = 600  # seconds the user has to get through GitHub's consent screen
# Where the React app runs. A login started from the app (/auth/login?app=true) ends there.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


@router.get("/login")
def login(app: bool = False):
    """Start GitHub login. app=true: the React app started it, so the callback sends the browser back
    to the app with the token. Without it the callback shows the token as JSON (handy in Swagger)."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "state": state,
    }
    github_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    response = RedirectResponse(github_url)
    # The callback only accepts the state stored in this browser, so nobody can finish
    # a login they started themselves inside someone else's browser (login CSRF)
    response.set_cookie(
        "oauth_state", state, max_age=STATE_MAX_AGE, httponly=True, samesite="lax",
        secure=REDIRECT_URI.startswith("https://"),
    )
    if app:
        response.set_cookie("login_target", "app", max_age=STATE_MAX_AGE, httponly=True, samesite="lax",
                            secure=REDIRECT_URI.startswith("https://"))
    return response


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    response: Response,
    oauth_state: str | None = Cookie(None),
    login_target: str | None = Cookie(None),
    db: Session = Depends(get_db),
):
    if not oauth_state or not secrets.compare_digest(state.encode(), oauth_state.encode()):
        raise HTTPException(status_code=400, detail="Invalid OAuth state - start again at /api/auth/login")
    response.delete_cookie("oauth_state")  # one login per state

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token from GitHub")

        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch GitHub user profile")
        github_user = user_response.json()

    github_user_id = github_user["id"]
    github_username = github_user["login"]
    email = github_user.get("email")

    encrypted = encrypt_token(access_token)

    # Match on GitHub's numeric id: a username can be renamed and later claimed by someone else
    user = db.query(User).filter(User.github_user_id == github_user_id).first()
    if not user:
        # one-time link for accounts created before github_user_id was stored
        user = db.query(User).filter(
            User.github_username == github_username, User.github_user_id.is_(None)
        ).first()
    if not user:
        user = User(
            github_user_id=github_user_id,
            github_username=github_username,
            email=email,
            github_access_token=encrypted,
        )
        db.add(user)
    else:
        user.github_user_id = github_user_id
        user.github_username = github_username  # follow GitHub username changes
        user.github_access_token = encrypted  # update on every login, in case the old token expired

    db.commit()
    db.refresh(user)
    jwt_token = create_access_token(str(user.id))
    if login_target == "app":
        # The token goes after '#': browsers never send that part to any server, so it stays out of
        # server logs and the Referer header. The app reads it and clears it from the address bar.
        redirect = RedirectResponse(f"{FRONTEND_URL}/auth/done#token={jwt_token}")
        redirect.delete_cookie("oauth_state")  # a new response object, so the cookies are cleared here
        redirect.delete_cookie("login_target")
        return redirect
    response.delete_cookie("login_target")
    return {"access_token": jwt_token, "token_type": "bearer", "github_username": user.github_username}
