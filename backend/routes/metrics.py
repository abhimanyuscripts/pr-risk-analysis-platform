from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database.connection import get_db
from database.models import Repository, PullRequest, Commit, ChangedFile, PRMetrics

router = APIRouter(prefix="/metrics", tags=["metrics"])

SENSITIVE_PATTERNS = ["auth", "login", "security", "payment", "migration", "password"]
TEST_PATTERNS = ["test_", "_test", "/tests/", "spec_", "_spec"]


def compute_metrics_for_pr(pull_request: PullRequest, db: Session) -> PRMetrics:
    changed_files = db.query(ChangedFile).filter(ChangedFile.pull_request_id == pull_request.id).all()
    commit_count = db.query(Commit).filter(Commit.pull_request_id == pull_request.id).count()

    lines_added = sum(f.additions for f in changed_files)
    lines_deleted = sum(f.deletions for f in changed_files)

    test_files_changed = sum(
        1 for f in changed_files if any(p in f.filename.lower() for p in TEST_PATTERNS)
    )
    is_sensitive = any(
        any(p in f.filename.lower() for p in SENSITIVE_PATTERNS) for f in changed_files
    )

    existing = db.query(PRMetrics).filter(PRMetrics.pull_request_id == pull_request.id).first()
    if existing:
        metrics = existing
    else:
        metrics = PRMetrics(pull_request_id=pull_request.id)
        db.add(metrics)

    metrics.files_changed = len(changed_files)
    metrics.lines_added = lines_added
    metrics.lines_deleted = lines_deleted
    metrics.churn = lines_added + lines_deleted
    metrics.commit_count = commit_count
    metrics.test_files_changed = test_files_changed
    metrics.is_sensitive_file = is_sensitive
    metrics.computed_at = datetime.now(timezone.utc)

    return metrics


@router.post("/compute/{owner}/{repo}")
def compute_metrics_for_repo(owner: str, repo: str, db: Session = Depends(get_db)):
    repository = db.query(Repository).filter(
        Repository.owner == owner, Repository.name == repo
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found — ingest it first")

    pull_requests = db.query(PullRequest).filter(PullRequest.repository_id == repository.id).all()

    computed_count = 0
    for pr in pull_requests:
        compute_metrics_for_pr(pr, db)
        computed_count += 1

    db.commit()

    return {"repository": repository.full_name, "metrics_computed": computed_count}