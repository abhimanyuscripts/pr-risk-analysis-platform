import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database.connection import get_db
from database.models import User
from auth.dependencies import get_current_user
from auth.encryption import decrypt_token
from database.models import Repository, PullRequest

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

@router.get("/repos/{owner}/{repo}/pulls")
async def list_pull_requests(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
):
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="No GitHub token stored for this user")

    token = decrypt_token(current_user.github_access_token)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers={"Authorization": f"Bearer {token}"},
            params={"state": "all", "per_page": 30, "sort": "updated"},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch pull requests from GitHub")

    prs = response.json()
    return [
        {
            "github_pr_number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "author_username": pr["user"]["login"],
            "created_at": pr["created_at"],
            "merged_at": pr["merged_at"],
            "base_branch": pr["base"]["ref"],
            "head_branch": pr["head"]["ref"],
        }
        for pr in prs
    ]

@router.post("/repos/{owner}/{repo}/ingest")
async def ingest_repository(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="No GitHub token stored for this user")

    token = decrypt_token(current_user.github_access_token)

    async with httpx.AsyncClient(timeout=15.0) as client:
        repo_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if repo_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch repository from GitHub")
        repo_data = repo_response.json()

        pr_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers={"Authorization": f"Bearer {token}"},
            params={"state": "all", "per_page": 30, "sort": "updated"},
        )
        if pr_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch pull requests from GitHub")
        prs_data = pr_response.json()

    # --- Upsert the repository ---
    repository = db.query(Repository).filter(Repository.github_repo_id == repo_data["id"]).first()
    if not repository:
        repository = Repository(
            added_by=current_user.id,
            owner=repo_data["owner"]["login"],
            name=repo_data["name"],
            full_name=repo_data["full_name"],
            github_repo_id=repo_data["id"],
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)

    # --- Upsert each PR ---
    created_count = 0
    updated_count = 0

    for pr in prs_data:
        # Derive our 3-value state from GitHub's state + merged flag
        if pr["state"] == "closed" and pr["merged_at"] is not None:
            our_state = "merged"
        else:
            our_state = pr["state"]

        existing = db.query(PullRequest).filter(
            PullRequest.repository_id == repository.id,
            PullRequest.github_pr_number == pr["number"],
        ).first()

        if existing:
            existing.state = our_state
            existing.merged_at = pr["merged_at"]
            updated_count += 1
        else:
            new_pr = PullRequest(
                repository_id=repository.id,
                github_pr_number=pr["number"],
                title=pr["title"],
                description=pr.get("body"),
                author_username=pr["user"]["login"],
                state=our_state,
                base_branch=pr["base"]["ref"],
                head_branch=pr["head"]["ref"],
                created_at=pr["created_at"],
                merged_at=pr["merged_at"],
            )
            db.add(new_pr)
            created_count += 1

    db.commit()

    return {
        "repository": repository.full_name,
        "prs_created": created_count,
        "prs_updated": updated_count,
    }