import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Repository, PullRequest, Commit, ChangedFile, PRLabel

router = APIRouter(prefix="/labels", tags=["labels"])

# v1: loose substring match on any file (kept unchanged so v1 and v2 can be compared)
FIX_PATTERNS = ["fix", "bug", "hotfix", "patch"]
WINDOW_DAYS = 60

# v2: whole-word match only (no "patch": it matches the HTTP PATCH method, "dispatch", mock patching)
FIX_REGEX = re.compile(r"\b(fix|fixes|fixed|bug|hotfix)\b", re.IGNORECASE)

# v2: files that many unrelated PRs touch (hubs) and that say nothing about code defects
NON_SOURCE_SUFFIXES = (".md", ".rst", ".txt", ".lock", ".yml", ".yaml")
NON_SOURCE_PREFIXES = ("docs/", ".github/")
NON_SOURCE_NAMES = ("changelog", "license", "requirements")


def is_source_file(filename: str) -> bool:
    lower = filename.lower()
    base = lower.rsplit("/", 1)[-1]
    if lower.startswith(NON_SOURCE_PREFIXES) or lower.endswith(NON_SOURCE_SUFFIXES):
        return False
    return not base.startswith(NON_SOURCE_NAMES)


def message_is_corrective(message: str | None, version: int) -> bool:
    if not message:
        return False
    if version == 1:
        return any(p in message.lower() for p in FIX_PATTERNS)
    return FIX_REGEX.search(message) is not None


def compute_label_for_pr(pr: PullRequest, all_prs: list[PullRequest], db: Session, version: int = 2) -> tuple[bool, list[str]]:
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
    # v2 only counts source files as overlap; v1 counts every file
    def overlap_files(pr_id):
        names = {f.filename for f in db.query(ChangedFile).filter(ChangedFile.pull_request_id == pr_id).all()}
        return names if version == 1 else {n for n in names if is_source_file(n)}

    my_files = overlap_files(pr.id)
    window_end = pr.merged_at + timedelta(days=WINDOW_DAYS)

    corrective_hit = False
    for other in all_prs:
        if other.id == pr.id or other.merged_at is None:
            continue
        if not (pr.merged_at < other.merged_at <= window_end):
            continue

        other_commits = db.query(Commit).filter(Commit.pull_request_id == other.id).all()
        is_corrective = any(message_is_corrective(c.message, version) for c in other_commits)
        if not is_corrective:
            continue

        if my_files & overlap_files(other.id):
            corrective_hit = True
            break

    if corrective_hit:
        reasons.append("corrective commit on touched file within window")

    is_risky = len(reasons) > 0
    if not reasons:
        reasons = ["no corrective activity detected within window"]

    return is_risky, reasons


@router.post("/compute/{owner}/{repo}")
def compute_labels_for_repo(owner: str, repo: str, version: int = 2, db: Session = Depends(get_db)):
    if version not in (1, 2):
        raise HTTPException(status_code=400, detail="version must be 1 or 2")

    repository = db.query(Repository).filter(Repository.owner == owner, Repository.name == repo).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found — ingest it first")

    all_prs = db.query(PullRequest).filter(PullRequest.repository_id == repository.id).all()

    # A PR's window is complete only if the data extends WINDOW_DAYS past its merge date.
    merged_times = [p.merged_at for p in all_prs if p.merged_at is not None]
    data_end = max(merged_times) if merged_times else None

    risky_count = 0
    usable_count = 0
    usable_risky = 0
    for pr in all_prs:
        is_risky, reasons = compute_label_for_pr(pr, all_prs, db, version)
        window_complete = (
            pr.state == "merged" and pr.merged_at is not None and data_end is not None
            and pr.merged_at + timedelta(days=WINDOW_DAYS) <= data_end
        )

        label = db.query(PRLabel).filter(
            PRLabel.pull_request_id == pr.id, PRLabel.label_version == version
        ).first()
        if not label:
            label = PRLabel(pull_request_id=pr.id, label_version=version)
            db.add(label)
        label.window_complete = window_complete

        label.is_risky = is_risky
        label.reasons = ", ".join(reasons)
        label.label_window_days = WINDOW_DAYS
        label.labeled_at = datetime.now(timezone.utc)

        if is_risky:
            risky_count += 1
        if window_complete:
            usable_count += 1
            if is_risky:
                usable_risky += 1

    db.commit()
    return {
        "repository": repository.full_name,
        "label_version": version,
        "total_prs": len(all_prs),
        "risky_prs": risky_count,
        "usable_prs": usable_count,  # merged with a complete window: what Phase 9 should train on
        "usable_risky_prs": usable_risky,
    }