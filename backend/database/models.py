import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    github_username = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    github_access_token = Column(String)

    repositories = relationship("Repository", back_populates="added_by_user")


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(511), nullable=False, unique=True)
    github_repo_id = Column(Integer, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    added_by_user = relationship("User", back_populates="repositories")
    pull_requests = relationship("PullRequest", back_populates="repository")


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_pr_number"),
        CheckConstraint("state IN ('open', 'closed', 'merged')"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False)
    github_pr_number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    author_username = Column(String(255), nullable=False)
    state = Column(String(20), nullable=False)
    base_branch = Column(String(255))
    head_branch = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False)
    merged_at = Column(DateTime(timezone=True))

    repository = relationship("Repository", back_populates="pull_requests")
    commits = relationship("Commit", back_populates="pull_request")
    changed_files = relationship("ChangedFile", back_populates="pull_request")
    pr_metrics = relationship("PRMetrics", back_populates="pull_request", uselist=False)


class Commit(Base):
    __tablename__ = "commits"
    __table_args__ = (UniqueConstraint("pull_request_id", "sha"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False)
    sha = Column(String(40), nullable=False)
    message = Column(Text)
    author = Column(String(255))
    committed_at = Column(DateTime(timezone=True))

    pull_request = relationship("PullRequest", back_populates="commits")


class ChangedFile(Base):
    __tablename__ = "changed_files"
    __table_args__ = (UniqueConstraint("pull_request_id", "filename"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False)
    filename = Column(String(1000), nullable=False)
    additions = Column(Integer, nullable=False, default=0)
    deletions = Column(Integer, nullable=False, default=0)
    status = Column(String(20))

    pull_request = relationship("PullRequest", back_populates="changed_files")


class PRMetrics(Base):
    __tablename__ = "pr_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    pull_request_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False, unique=True)
    files_changed = Column(Integer)
    lines_added = Column(Integer)
    lines_deleted = Column(Integer)
    churn = Column(Integer)
    commit_count = Column(Integer)
    test_files_changed = Column(Integer)
    is_sensitive_file = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime(timezone=True))

    pull_request = relationship("PullRequest", back_populates="pr_metrics")