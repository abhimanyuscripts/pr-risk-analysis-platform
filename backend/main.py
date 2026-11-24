"""The whole site in one process: the API under /api and the built React app everywhere else.

Production (Render) and `docker compose` serve both from here, so the browser talks to a single
address and no CORS is involved. In development Vite serves the app on :5173 and forwards /api here.
"""
import logging
import os

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.connection import get_db
from database.models import User
from routes.auth import router as auth_router
from routes.github import router as github_router
from routes.labels import router as labels_router
from routes.metrics import router as metrics_router
from routes.repos import router as repos_router
from settings import allowed_writers, app_env, production_problems, static_dir

logger = logging.getLogger("uvicorn.error")

# Refuse to start a public site with laptop secrets or a half-finished configuration.
if app_env() == "production":
    problems = production_problems()
    if problems:
        raise RuntimeError("Not safe to start in production:\n- " + "\n- ".join(problems))
    if not allowed_writers():
        logger.info("ALLOWED_WRITERS is empty: the site is read-only (no ingest, metrics or label runs)")

app = FastAPI(
    title="PR Risk API",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# Only needed when the app is served from another address than the API (e.g. VITE_API_URL set).
FRONTEND_ORIGINS = [o.strip() for o in os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],  # the token travels in a header, not a cookie
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if app_env() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


api = APIRouter(prefix="/api")
api.include_router(auth_router)
api.include_router(github_router)
api.include_router(metrics_router)
api.include_router(labels_router)
api.include_router(repos_router)


@api.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    """For the host's health check and uptime monitors: is the API up and can it reach the database?"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return {"status": "ok", "database": "connected"}


@api.get("/users/me", tags=["auth"])
def read_current_user(current_user: User = Depends(get_current_user)):
    # can_write tells the page which message is true for this account: writers can ingest a
    # repository through the API, everyone else can only read what is stored.
    return {
        "github_username": current_user.github_username,
        "user_id": str(current_user.id),
        "can_write": current_user.github_username.lower() in allowed_writers(),
    }


app.include_router(api)


# ---- the React app ----

# The page itself may only load files from this site. Inline style attributes are allowed because
# React sets some (bar widths); no inline scripts are allowed. data: fonts are allowed because Vite
# inlines the smallest font files into the CSS. Swagger (/api/docs) is not covered.
APP_CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
           "connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def frontend(path: str):
    """Files from the React build, and index.html for every app page (/repos/..., /login, ...)."""
    if path == "api" or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")  # an unknown API path stays JSON
    root = static_dir()
    index = root / "index.html"
    if not index.is_file():
        if path == "":
            return {"status": "ok", "api_docs": "/api/docs",
                    "frontend": "not built here: run `npm run dev` in frontend/ (or use Docker)"}
        raise HTTPException(status_code=404, detail="Not found")

    try:
        candidate = (root / path).resolve()
        is_file = bool(path) and candidate.is_file() and candidate.is_relative_to(root)  # never outside the build
    except (OSError, ValueError):  # e.g. a NUL byte or an over-long name in the address
        is_file = False
    if is_file:
        # Vite puts a content hash in every file name under assets/, so those can be cached forever.
        cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "public, max-age=3600"
        return FileResponse(candidate, headers={"Cache-Control": cache})
    if path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not found")  # a missing script must not get HTML
    return FileResponse(index, headers={"Cache-Control": "no-cache", "Content-Security-Policy": APP_CSP})
