import asyncio
import logging
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database.models import Commit
from database.connection import get_db
from database.models import User
from auth.dependencies import get_current_user, get_github_token
from database.models import Repository, PullRequest
from database.models import ChangedFile


logger = logging.getLogger("uvicorn.error")  # shows up in the uvicorn terminal
COMMIT_EVERY = 50  # PRs per DB commit, so a crash loses at most this many

router = APIRouter(prefix="/github", tags=["github"])

PER_PAGE = 100  # GitHub's maximum page size
MAX_PAGES = 100  # safety cap so a bug can never loop forever
MAX_RATE_LIMIT_WAIT = 3600  # seconds; GitHub's hourly limit always resets within this


class GitHubFetchError(Exception):
    """A GitHub request for one PR's data failed, so that PR must be reported, not stored as empty."""


async def github_get(client: httpx.AsyncClient, url: str, token: str, params: dict | None = None) -> httpx.Response:
    """GET from the GitHub API. If a rate limit is hit, wait until it resets and retry once."""
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(url, headers=headers, params=params)
    if response.status_code not in (403, 429):
        return response

    if "retry-after" in response.headers:  # secondary rate limit
        wait = int(response.headers["retry-after"])
    elif response.headers.get("x-ratelimit-remaining") == "0":  # hourly limit (5,000 requests)
        wait = int(response.headers["x-ratelimit-reset"]) - time.time() + 1
    else:
        return response  # a real 403, e.g. no access to the repo
    if wait > MAX_RATE_LIMIT_WAIT:
        return response

    logger.warning("GitHub rate limit hit, waiting %.0fs before retrying", wait)
    await asyncio.sleep(max(wait, 0))
    return await client.get(url, headers=headers, params=params)


async def fetch_all_pages(client: httpx.AsyncClient, url: str, token: str, params: dict | None = None):
    """Fetch every page of a GitHub list endpoint.

    GitHub has no explicit "last page" flag in the body, so we stop when a page
    returns fewer than PER_PAGE items. Returns None if any request fails, so
    callers decide whether that is fatal.
    """
    items = []
    for page in range(1, MAX_PAGES + 1):
        response = await github_get(
            client, url, token, params={**(params or {}), "per_page": PER_PAGE, "page": page}
        )
        if response.status_code != 200:
            logger.warning("GitHub returned %d for %s (page %d)", response.status_code, url, page)
            return None
        batch = response.json()
        items.extend(batch)
        if len(batch) < PER_PAGE:
            break
    return items


@router.get("/repos")
async def list_repos(token: str = Depends(get_github_token)):
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
    token: str = Depends(get_github_token),
):
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
    token: str = Depends(get_github_token),
    db: Session = Depends(get_db),
):
    async with httpx.AsyncClient(timeout=15.0) as client:
        repo_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if repo_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch repository from GitHub")
        repo_data = repo_response.json()

        prs_data = await fetch_all_pages(
            client,
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            token,
            params={"state": "all", "sort": "created", "direction": "asc"},
        )
        if prs_data is None:
            raise HTTPException(status_code=502, detail="Failed to fetch pull requests from GitHub")

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

        # --- Upsert each PR, and ingest its commits ---
        created_count = 0
        updated_count = 0
        total_commits = 0
        total_files = 0
        

        logger.info("Ingest %s: fetched %d PRs, starting", repository.full_name, len(prs_data))
        failed_prs = []

        for i, pr in enumerate(prs_data, start=1):
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
                pull_request_obj = existing
            else:
                new_pr = PullRequest(
                    repository_id=repository.id,
                    github_pr_number=pr["number"],
                    title=pr["title"],
                    description=pr.get("body"),
                    author_username=(pr.get("user") or {}).get("login", "ghost"),  # deleted users come back as null
                    state=our_state,
                    base_branch=pr["base"]["ref"],
                    head_branch=pr["head"]["ref"],
                    created_at=pr["created_at"],
                    merged_at=pr["merged_at"],
                )
                db.add(new_pr)
                created_count += 1
                pull_request_obj = new_pr

            db.flush()  # assigns pull_request_obj.id so commits can reference it via foreign key

            try:
                total_commits += await ingest_commits_for_pr(
                    client, token, owner, repo, pr["number"], pull_request_obj, db
                )
                total_files += await ingest_changed_files_for_pr(
                    client, token, owner, repo, pr["number"], pull_request_obj, db
                )
            except (httpx.HTTPError, GitHubFetchError) as e:  # network errors / non-200s: skip this PR, keep going
                logger.warning("PR #%s: commits/files skipped: %r", pr["number"], e)
                failed_prs.append(pr["number"])

            if i % COMMIT_EVERY == 0:
                db.commit()
                logger.info("Ingest progress: %d/%d PRs", i, len(prs_data))

        db.commit()
        logger.info("Ingest done: %d PRs, %d failed", len(prs_data), len(failed_prs))

        return {
            "repository": repository.full_name,
            "prs_created": created_count,
            "prs_updated": updated_count,
            "commits_ingested": total_commits,
            "files_ingested": total_files,
            "failed_prs": failed_prs,
        }

async def ingest_commits_for_pr(client: httpx.AsyncClient, token: str, owner: str, repo: str, pr_number: int, pull_request: PullRequest, db: Session):
    commits_data = await fetch_all_pages(
        client, f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits", token
    )
    if commits_data is None:  # the caller records this PR in failed_prs and carries on
        raise GitHubFetchError(f"could not fetch commits for PR #{pr_number}")

    count = 0

    for c in commits_data:
        existing = db.query(Commit).filter(
            Commit.pull_request_id == pull_request.id,
            Commit.sha == c["sha"],
        ).first()

        if not existing:
            new_commit = Commit(
                pull_request_id=pull_request.id,
                sha=c["sha"],
                message=c["commit"]["message"],
                author=c["commit"]["author"]["name"] if c["commit"]["author"] else None,
                committed_at=c["commit"]["author"]["date"] if c["commit"]["author"] else None,
            )
            db.add(new_commit)
            count += 1

    return count

async def ingest_changed_files_for_pr(client: httpx.AsyncClient, token: str, owner: str, repo: str, pr_number: int, pull_request: PullRequest, db: Session):
    files_data = await fetch_all_pages(
        client, f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files", token
    )
    if files_data is None:
        raise GitHubFetchError(f"could not fetch changed files for PR #{pr_number}")

    count = 0

    for f in files_data:
        existing = db.query(ChangedFile).filter(
            ChangedFile.pull_request_id == pull_request.id,
            ChangedFile.filename == f["filename"],
        ).first()

        if not existing:
            new_file = ChangedFile(
                pull_request_id=pull_request.id,
                filename=f["filename"],
                additions=f["additions"],
                deletions=f["deletions"],
                status=f["status"],
            )
            db.add(new_file)
            count += 1

    return count
