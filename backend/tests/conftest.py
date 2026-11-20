"""Shared test setup (Phase 17).

The tests need their OWN PostgreSQL database, because they create and empty tables on every run.
Set TEST_DATABASE_URL (in backend/.env or the shell) to a database whose name ends in "_test",
for example postgresql://pr_risk_app:<password>@localhost:5432/pr_risk_test.
Anything else is refused, so the real pr_risk_dev data can never be touched by a test.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
from cryptography.fernet import Fernet
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND / ".env")  # only to find TEST_DATABASE_URL; everything below is overridden

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
_db_name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
if not _db_name.endswith("_test"):
    raise pytest.UsageError(
        "Set TEST_DATABASE_URL to a separate database whose name ends in '_test' "
        "(e.g. .../pr_risk_test). The tests empty its tables, so it must not be your real database."
    )

# Fixed settings for every test, set BEFORE the app is imported. The app's own load_dotenv()
# never overrides a variable that is already set, so the real secrets in .env are not used.
os.environ.update(
    DATABASE_URL=TEST_DATABASE_URL,
    JWT_SECRET_KEY="test-jwt-secret",
    TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    GITHUB_CLIENT_ID="test-client-id",
    GITHUB_CLIENT_SECRET="test-client-secret",
    GITHUB_REDIRECT_URI="http://localhost:8000/auth/callback",
    GITHUB_OAUTH_SCOPE="read:user",
    GEMINI_MODEL="test-model",
    FRONTEND_URL="http://localhost:5173",
    FRONTEND_ORIGINS="http://localhost:5173,http://localhost:3000",
)
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import main  # noqa: E402
from auth.jwt_handler import create_access_token  # noqa: E402
from database.connection import Base, engine  # noqa: E402
from database.models import (ChangedFile, Commit, LLMAnalysis, PRLabel, PRMetrics,  # noqa: E402
                             PullRequest, Repository, User)

MODEL = "test-model"  # the "research model" as far as the API is concerned in these tests
TABLES = [User, Repository, PullRequest, Commit, ChangedFile, PRMetrics, PRLabel, LLMAnalysis]


@pytest.fixture(scope="session", autouse=True)
def schema():
    """Create the tables the API uses once per run (pgvector tables are not needed)."""
    tables = [t.__table__ for t in TABLES]
    Base.metadata.drop_all(engine, tables=tables)
    Base.metadata.create_all(engine, tables=tables)
    yield
    Base.metadata.drop_all(engine, tables=tables)


@pytest.fixture(autouse=True)
def empty_tables():
    """Every test starts from empty tables."""
    yield
    names = ", ".join(t.__tablename__ for t in TABLES)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session


@pytest.fixture
def client():
    return TestClient(main.app)


def dt(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=timezone.utc)


def auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


class Seed:
    """Small helpers to put rows in the test database."""

    def __init__(self, db: Session):
        self.db = db

    def user(self, name: str, github_id: int) -> User:
        u = User(github_username=name, github_user_id=github_id)
        self.db.add(u)
        self.db.flush()
        return u

    def repo(self, user: User, owner: str, name: str, github_id: int) -> Repository:
        r = Repository(added_by=user.id, owner=owner, name=name, full_name=f"{owner}/{name}", github_repo_id=github_id)
        self.db.add(r)
        self.db.flush()
        return r

    def pr(self, repo: Repository, number: int, merged: datetime | None, state: str = "merged", **kw) -> PullRequest:
        p = PullRequest(repository_id=repo.id, github_pr_number=number, title=f"PR {number}", author_username="dev",
                        state=state, created_at=dt(2024, 1, 1), merged_at=merged, **kw)
        self.db.add(p)
        self.db.flush()
        return p

    def metrics(self, pr: PullRequest, churn: int, files: int = 2) -> None:
        self.db.add(PRMetrics(pull_request_id=pr.id, files_changed=files, lines_added=churn, lines_deleted=0,
                              churn=churn, commit_count=1, test_files_changed=0))

    def label(self, pr: PullRequest, version: int, risky: bool, complete: bool = True, reasons: str | None = None) -> None:
        self.db.add(PRLabel(pull_request_id=pr.id, label_version=version, is_risky=risky,
                            window_complete=complete, reasons=reasons))

    def llm(self, pr: PullRequest, score: int, level: str = "low", rag: bool = True, model: str = MODEL,
            prompt_version: int = 1, **kw) -> None:
        self.db.add(LLMAnalysis(pull_request_id=pr.id, model=model, prompt_version=prompt_version, use_rag=rag,
                                risk_score=score, risk_level=level, result=kw.pop("result", {}), **kw))

    def file(self, pr: PullRequest, name: str, add: int, delete: int, patch: str | None = None) -> None:
        self.db.add(ChangedFile(pull_request_id=pr.id, filename=name, additions=add, deletions=delete,
                                status="modified", patch=patch))


@pytest.fixture
def seed(db):
    return Seed(db)


@pytest.fixture
def world(seed, db):
    """Two users, each with one repo. User A's repo has 7 PRs covering the awkward cases:
    no metrics (5), no label (5, 6), an incomplete window (4), only a no-docs answer (3),
    an answer from another model (4), an open PR (6) and tied churn (2 and 7)."""
    a, b = seed.user("alice", 1), seed.user("bob", 2)
    ra, rb = seed.repo(a, "encode", "httpx", 101), seed.repo(b, "acme", "secret", 202)
    prs = {
        1: seed.pr(ra, 1, dt(2024, 1, 1)), 2: seed.pr(ra, 2, dt(2024, 2, 1)), 3: seed.pr(ra, 3, dt(2024, 3, 1)),
        4: seed.pr(ra, 4, dt(2024, 4, 1)), 5: seed.pr(ra, 5, dt(2024, 5, 1)), 6: seed.pr(ra, 6, None, "open"),
        7: seed.pr(ra, 7, dt(2024, 6, 1)),
    }
    for n, churn in [(1, 5), (2, 50), (3, 500), (4, 20), (6, 7), (7, 50)]:
        seed.metrics(prs[n], churn)
    seed.label(prs[1], 3, False)
    seed.label(prs[1], 2, True)
    seed.label(prs[2], 3, True)
    seed.label(prs[3], 3, True)
    seed.label(prs[4], 3, False, complete=False)
    seed.label(prs[7], 3, False)
    seed.llm(prs[1], 10)
    seed.llm(prs[2], 70, "high")
    seed.llm(prs[2], 30, "medium", rag=False)
    seed.llm(prs[3], 90, "high", rag=False)
    seed.llm(prs[4], 40, "medium", model="other-model")
    seed.llm(prs[6], 55, "medium")
    seed.llm(prs[7], 70, "high")
    q1 = seed.pr(rb, 1, dt(2024, 7, 1))
    seed.metrics(q1, 9)
    db.commit()
    return {"a": a, "b": b, "prs": prs}
