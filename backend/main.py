import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from routes.auth import router as auth_router
from auth.dependencies import get_current_user
from database.models import User
from database.connection import get_db
from routes.github import router as github_router
from routes.metrics import router as metrics_router
from routes.labels import router as labels_router
from routes.repos import router as repos_router


app = FastAPI()

# The React dev server runs on its own port, so the browser treats it as a different origin and blocks its
# calls unless this API says it is allowed. 5173 = Vite's default port, 3000 = the other common one.
# Override with FRONTEND_ORIGINS="https://your-site,..." (comma-separated) when deploying.
FRONTEND_ORIGINS = [o.strip() for o in os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],  # the token travels in a header, not a cookie
)
app.include_router(auth_router)
app.include_router(github_router)
app.include_router(metrics_router)
app.include_router(labels_router)
app.include_router(repos_router)

@app.get("/")
def read_root():
    return {"status": "ok", "project": "pr-risk-analysis-platform"}

@app.get("/health/db")
def health_check_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "connected"}

@app.get("/users/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return {"github_username": current_user.github_username, "user_id": str(current_user.id)}