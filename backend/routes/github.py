import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from auth.dependencies import get_current_user
from auth.encryption import decrypt_token

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/repos")
async def list_repos(current_user: User = Depends(get_current_user)):
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="No GitHub token stored for this user")

    token = decrypt_token(current_user.github_access_token)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.github.com/user/repos",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 30, "sort": "updated"},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch repositories from GitHub")

    repos = response.json()
    return [
        {
            "github_repo_id": repo["id"],
            "full_name": repo["full_name"],
            "private": repo["private"],
            "updated_at": repo["updated_at"],
        }
        for repo in repos
    ]