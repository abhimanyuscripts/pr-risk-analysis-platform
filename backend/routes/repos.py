"""Phase 16a: read-only endpoints for the dashboard.

They serve only what is already stored (nothing here calls GitHub or the LLM), and a user
only sees repositories they added themselves, so a private repo never leaks to another login.
"""
import os
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from auth.dependencies import get_current_user
from database.connection import get_db
from database.models import ChangedFile, LLMAnalysis, PRLabel, PRMetrics, PullRequest, Repository, User
from llm.prompt import PROMPT_VERSION

router = APIRouter(prefix="/repos", tags=["repos"])

# The model the research used (GEMINI_MODEL in backend/.env). Read from the environment instead of
# importing llm.client, so that starting the API does not load the Gemini library.
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
DEFAULT_LABEL_VERSION = 3  # the main label since Phase 10


# ---- response shapes: what the React app receives (they also appear in /docs) ----

class RepoOut(BaseModel):
    owner: str
    name: str
    full_name: str
    pr_count: int
    last_merged_at: datetime | None
    llm_analyzed_count: int  # PRs that have at least one stored LLM answer


class LabelOut(BaseModel):
    version: int
    is_risky: bool
    window_complete: bool  # False = too recent to know yet; do not read is_risky as a result


class LLMOut(BaseModel):
    risk_score: int
    risk_level: str
    use_rag: bool


class PRListItem(BaseModel):
    number: int
    title: str
    author: str
    state: str
    merged_at: datetime | None
    files_changed: int | None
    churn: int | None
    label: LabelOut | None  # None = this label version was never computed for the PR
    llm: LLMOut | None      # None = no stored LLM answer yet


class PRListOut(BaseModel):
    total: int  # matching PRs before paging, so the UI can show "51-100 of 1,294"
    limit: int
    offset: int
    items: list[PRListItem]


class MetricsOut(BaseModel):
    files_changed: int | None
    lines_added: int | None
    lines_deleted: int | None
    churn: int | None
    commit_count: int | None
    test_files_changed: int | None
    is_sensitive_file: bool


class LabelDetail(LabelOut):
    window_days: int
    reasons: str | None  # why it was labelled risky; this is hindsight, not something known at merge time


class ConcernOut(BaseModel):
    category: str
    file: str
    explanation: str


class DocChunkOut(BaseModel):
    heading: str | None
    distance: float  # cosine distance, 0 = same meaning; lower = closer match


class LLMDetail(BaseModel):
    model: str
    prompt_version: int
    use_rag: bool
    risk_score: int
    risk_level: str
    summary: str
    concerns: list[ConcernOut]
    tests_included: bool | None
    diff_truncated: bool          # True = the LLM saw only part of the diff
    retrieved_docs: list[DocChunkOut]  # RAG only: the doc sections put in the prompt
    created_at: datetime | None


class FileOut(BaseModel):
    filename: str
    status: str | None
    additions: int
    deletions: int
    has_diff: bool  # the diff itself is not sent: it can be very large


class PRDetailOut(BaseModel):
    number: int
    title: str
    description: str | None
    author: str
    state: str
    base_branch: str | None
    head_branch: str | None
    created_at: datetime
    merged_at: datetime | None
    github_url: str
    metrics: MetricsOut | None
    labels: list[LabelDetail]  # every computed version, newest version first
    llm_analyses: list[LLMDetail]  # the research model's RAG answer first, then the rest
    files: list[FileOut]  # biggest change first


# ---- helpers ----

def get_own_repo(db: Session, user: User, owner: str, repo: str) -> Repository:
    """The repo, but only if this user added it. Someone else's repo answers 404, the same
    as a repo that does not exist, so the API never confirms that a private repo is there."""
    repository = db.query(Repository).filter(
        Repository.owner == owner, Repository.name == repo, Repository.added_by == user.id
    ).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository


# ---- endpoints ----

@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The repositories this user has ingested (stored data, not the live GitHub list)."""
    rows = (
        db.query(Repository, func.count(PullRequest.id), func.max(PullRequest.merged_at))
        .outerjoin(PullRequest, PullRequest.repository_id == Repository.id)
        .filter(Repository.added_by == current_user.id)
        .group_by(Repository.id)
        .order_by(Repository.full_name)
        .all()
    )
    analyzed = {}
    if rows:
        analyzed = dict(
            db.query(PullRequest.repository_id, func.count(func.distinct(LLMAnalysis.pull_request_id)))
            .join(LLMAnalysis, LLMAnalysis.pull_request_id == PullRequest.id)
            .filter(PullRequest.repository_id.in_([r.id for r, _, _ in rows]))
            .group_by(PullRequest.repository_id)
            .all()
        )
    return [
        RepoOut(owner=r.owner, name=r.name, full_name=r.full_name, pr_count=pr_count,
                last_merged_at=last_merged, llm_analyzed_count=analyzed.get(r.id, 0))
        for r, pr_count, last_merged in rows
    ]


@router.get("/{owner}/{repo}/prs", response_model=PRListOut)
def list_prs(
    owner: str,
    repo: str,
    sort: Literal["merged_at", "churn", "llm_score"] = "merged_at",
    desc: bool = True,
    risky: bool | None = Query(None, description="Only PRs whose label says risky (true) or not (false)"),
    label_version: int = Query(DEFAULT_LABEL_VERSION, ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One page of a repo's PRs with their metrics, label and (if stored) LLM score."""
    repository = get_own_repo(db, current_user, owner, repo)

    label = aliased(PRLabel)
    llm = aliased(LLMAnalysis)
    # Each join matches at most one row per PR (metrics, label per version, and one LLM answer per
    # model + prompt version + RAG setting are all unique in the schema), so the page never gets
    # duplicate PRs. Outer joins keep PRs that have no label or no LLM answer yet.
    base = (
        db.query(PullRequest)
        .outerjoin(PRMetrics, PRMetrics.pull_request_id == PullRequest.id)
        .outerjoin(label, (label.pull_request_id == PullRequest.id) & (label.label_version == label_version))
        .outerjoin(llm, (llm.pull_request_id == PullRequest.id) & (llm.model == LLM_MODEL)
                   & (llm.prompt_version == PROMPT_VERSION) & llm.use_rag.is_(True))
        .filter(PullRequest.repository_id == repository.id)
    )
    if risky is not None:
        base = base.filter(label.is_risky == risky)
    total = base.count()

    column = {"merged_at": PullRequest.merged_at, "churn": PRMetrics.churn, "llm_score": llm.risk_score}[sort]
    ordering = column.desc().nulls_last() if desc else column.asc().nulls_last()
    rows = (
        base.with_entities(PullRequest, PRMetrics, label, llm)
        .order_by(ordering, PullRequest.github_pr_number.desc())  # PR number breaks ties, so paging is stable
        .limit(limit).offset(offset).all()
    )
    items = [
        PRListItem(
            number=pr.github_pr_number, title=pr.title, author=pr.author_username, state=pr.state,
            merged_at=pr.merged_at,
            files_changed=m.files_changed if m else None, churn=m.churn if m else None,
            label=LabelOut(version=lab.label_version, is_risky=lab.is_risky,
                           window_complete=lab.window_complete) if lab else None,
            llm=LLMOut(risk_score=a.risk_score, risk_level=a.risk_level, use_rag=a.use_rag) if a else None,
        )
        for pr, m, lab, a in rows
    ]
    return PRListOut(total=total, limit=limit, offset=offset, items=items)


@router.get("/{owner}/{repo}/prs/{number}", response_model=PRDetailOut)
def get_pr(owner: str, repo: str, number: int, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    """Everything stored about one PR: metrics, labels, LLM answers with their reasons, files."""
    repository = get_own_repo(db, current_user, owner, repo)
    pr = db.query(PullRequest).filter(
        PullRequest.repository_id == repository.id, PullRequest.github_pr_number == number
    ).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")

    m = db.query(PRMetrics).filter(PRMetrics.pull_request_id == pr.id).first()
    labels = (db.query(PRLabel).filter(PRLabel.pull_request_id == pr.id)
              .order_by(PRLabel.label_version.desc()).all())
    analyses = db.query(LLMAnalysis).filter(LLMAnalysis.pull_request_id == pr.id).all()
    # the answer the dashboard headlines (research model, current prompt, RAG) comes first
    analyses.sort(key=lambda a: (not (a.model == LLM_MODEL and a.prompt_version == PROMPT_VERSION and a.use_rag),
                                 a.model, -a.prompt_version, not a.use_rag))
    files = (db.query(ChangedFile).filter(ChangedFile.pull_request_id == pr.id)
             .order_by((ChangedFile.additions + ChangedFile.deletions).desc(), ChangedFile.filename).all())

    def llm_detail(a: LLMAnalysis) -> LLMDetail:
        r = a.result or {}
        return LLMDetail(
            model=a.model, prompt_version=a.prompt_version, use_rag=a.use_rag,
            risk_score=a.risk_score, risk_level=a.risk_level,
            summary=r.get("summary", ""),
            concerns=[ConcernOut(category=c.get("category", ""), file=c.get("file", ""),
                                 explanation=c.get("explanation", "")) for c in r.get("concerns", [])],
            tests_included=r.get("tests_included"),
            diff_truncated=a.diff_truncated,
            retrieved_docs=[DocChunkOut(heading=c.get("heading"), distance=c.get("distance", 0.0))
                            for c in (a.retrieved_chunks or [])],
            created_at=a.created_at,
        )

    return PRDetailOut(
        number=pr.github_pr_number, title=pr.title, description=pr.description,
        author=pr.author_username, state=pr.state, base_branch=pr.base_branch, head_branch=pr.head_branch,
        created_at=pr.created_at, merged_at=pr.merged_at,
        github_url=f"https://github.com/{repository.full_name}/pull/{pr.github_pr_number}",
        metrics=MetricsOut(files_changed=m.files_changed, lines_added=m.lines_added, lines_deleted=m.lines_deleted,
                           churn=m.churn, commit_count=m.commit_count, test_files_changed=m.test_files_changed,
                           is_sensitive_file=m.is_sensitive_file) if m else None,
        labels=[LabelDetail(version=lab.label_version, is_risky=lab.is_risky, window_complete=lab.window_complete,
                            window_days=lab.label_window_days, reasons=lab.reasons) for lab in labels],
        llm_analyses=[llm_detail(a) for a in analyses],
        files=[FileOut(filename=f.filename, status=f.status, additions=f.additions, deletions=f.deletions,
                       has_diff=f.patch is not None) for f in files],
    )
