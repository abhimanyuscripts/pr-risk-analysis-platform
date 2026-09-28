from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Repository, PullRequest, Commit, ChangedFile, PRLabel

router = APIRouter(prefix="/labels", tags=["labels"])

FIX_PATTERNS = ["fix", "bug", "hotfix", "patch"]
WINDOW_DAYS = 60


def compute_label_for_pr(pr: PullRequest, all_prs: list[PullRequest], db: Session) -> tuple[bool, list[str]]:
    reasons = []

    if pr.state != "merged" or pr.merged_at is None:
        return False, ["not merged — not eligible for labeling"]

    # --- Signal 1: explicit revert ---
    revert_title = f'Revert "{pr.title}"'
    was_reverted = any(
        other.title.strip() == revert_title and other.state == "merged"
        for other in all_prs if other.id != pr.id
    )
    if was_reverted:
        reasons.append("reverted")

    # --- Signal 2: corrective commit on a touched file, within the window ---
    my_files = {f.filename for f in db.query(ChangedFile).filter(ChangedFile.pull_request_id == pr.id).all()}
    window_end = pr.merged_at + timedelta(days=WINDOW_DAYS)

    corrective_hit = False
    for other in all_prs:
        if other.id == pr.id or other.merged_at is None:
            continue
        if not (pr.merged_at < other.merged_at <= window_end):
            continue

        other_commits = db.query(Commit).filter(Commit.pull_request_id == other.id).all()
        is_corrective = any(
            c.message and any(p in c.message.lower() for p in FIX_PATTERNS) for c in other_commits
        )
        if not is_corrective:
            continue

        other_files = {f.filename for f in db.query(ChangedFile).filter(ChangedFile.pull_request_id == other.id).all()}
        if my_files & other_files:
            corrective_hit = True
            break

    if corrective_hit:
        reasons.append("corrective commit on touched file within window")

    is_risky = len(reasons) > 0
    if not reasons:
        reasons = ["no corrective activity detected within window"]

    return is_risky, reasons


@router.post("/compute/{owner}/{repo}")
def compute_labels_for_repo(owner: str, repo: str, db: Session = Depends(get_db)):
    repository = db.query(Repository).filter(Repository.owner == owner, Repository.name == repo).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found — ingest it first")

    all_prs = db.query(PullRequest).filter(PullRequest.repository_id == repository.id).all()

    risky_count = 0
    for pr in all_prs:
        is_risky, reasons = compute_label_for_pr(pr, all_prs, db)

        label = db.query(PRLabel).filter(PRLabel.pull_request_id == pr.id).first()
        if not label:
            label = PRLabel(pull_request_id=pr.id)
            db.add(label)

        label.is_risky = is_risky
        label.reasons = ", ".join(reasons)
        label.label_window_days = WINDOW_DAYS
        label.labeled_at = datetime.now(timezone.utc)

        if is_risky:
            risky_count += 1

    db.commit()
    return {"repository": repository.full_name, "total_prs": len(all_prs), "risky_prs": risky_count}