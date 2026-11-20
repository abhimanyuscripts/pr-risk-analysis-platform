"""Deployment settings that more than one module needs (Phase 19).

They are read from the environment on every call, not once at import, so a test can change them
with monkeypatch.setenv and a value in backend/.env is picked up the same way as the others.
"""
import os
from pathlib import Path

from cryptography.fernet import Fernet

BACKEND_DIR = Path(__file__).resolve().parent


def _csv(name: str) -> set[str]:
    return {part.strip().lower() for part in os.getenv(name, "").split(",") if part.strip()}


def app_env() -> str:
    """'production' on the deployed site; anything else counts as development."""
    return os.getenv("APP_ENV", "development").strip().lower()


def public_repos() -> set[str]:
    """Repositories ("owner/name", any case) that anyone may read without logging in: the demo."""
    return _csv("PUBLIC_REPOS")


def allowed_writers() -> set[str]:
    """GitHub usernames allowed to ingest data or recompute metrics and labels. Empty = nobody:
    a deployed site stays read-only unless its owner names who may write."""
    return _csv("ALLOWED_WRITERS")


def static_dir() -> Path:
    """Where the built React app (frontend/dist) is served from. The Docker image copies it here."""
    return Path(os.getenv("STATIC_DIR", BACKEND_DIR / "static")).resolve()


# Values that were ever used on a laptop or in tests; a deployed site must not reuse them.
_KNOWN_DEV_SECRETS = {"test-jwt-secret", "change_me", "changeme", "secret", "dev"}


def production_problems() -> list[str]:
    """Everything that makes the current environment unsafe to run as the public site."""
    problems = []
    if not os.getenv("DATABASE_URL"):
        problems.append("DATABASE_URL is not set")
    jwt_key = os.getenv("JWT_SECRET_KEY", "")
    if len(jwt_key) < 32 or jwt_key.lower() in _KNOWN_DEV_SECRETS:
        problems.append("JWT_SECRET_KEY must be a new random value of at least 32 characters")
    try:
        Fernet(os.getenv("TOKEN_ENCRYPTION_KEY", "").encode())
    except ValueError:
        problems.append("TOKEN_ENCRYPTION_KEY is not a valid Fernet key")
    for name in ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"):
        if not os.getenv(name):
            problems.append(f"{name} is not set")
    redirect = os.getenv("GITHUB_REDIRECT_URI", "")
    if not (redirect.startswith("https://") and redirect.endswith("/api/auth/callback")):
        problems.append("GITHUB_REDIRECT_URI must be https://<your-site>/api/auth/callback")
    if not os.getenv("FRONTEND_URL", "").startswith("https://"):
        problems.append("FRONTEND_URL must be the https:// address of the site")
    return problems
