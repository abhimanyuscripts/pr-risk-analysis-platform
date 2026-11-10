-- USERS
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_username VARCHAR(255) NOT NULL UNIQUE,
    email           VARCHAR(255) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- REPOSITORIES
CREATE TABLE repositories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    added_by        UUID NOT NULL REFERENCES users(id),
    owner           VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    full_name       VARCHAR(511) NOT NULL UNIQUE,
    github_repo_id  BIGINT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_repositories_added_by ON repositories(added_by);

-- PULL_REQUESTS
CREATE TABLE pull_requests (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id      UUID NOT NULL REFERENCES repositories(id),
    github_pr_number   INT NOT NULL,
    title              VARCHAR(500) NOT NULL,
    description        TEXT,
    author_username    VARCHAR(255) NOT NULL,
    state              VARCHAR(20) NOT NULL CHECK (state IN ('open', 'closed', 'merged')),
    base_branch        VARCHAR(255),
    head_branch        VARCHAR(255),
    created_at         TIMESTAMPTZ NOT NULL,
    merged_at          TIMESTAMPTZ,
    UNIQUE (repository_id, github_pr_number)
);
CREATE INDEX idx_pull_requests_repository_id ON pull_requests(repository_id);
CREATE INDEX idx_pull_requests_merged_at ON pull_requests(merged_at);

-- COMMITS
CREATE TABLE commits (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id   UUID NOT NULL REFERENCES pull_requests(id),
    sha               VARCHAR(40) NOT NULL,
    message           TEXT,
    author            VARCHAR(255),
    committed_at      TIMESTAMPTZ,
    UNIQUE (pull_request_id, sha)
);
CREATE INDEX idx_commits_pull_request_id ON commits(pull_request_id);

-- CHANGED_FILES
CREATE TABLE changed_files (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id   UUID NOT NULL REFERENCES pull_requests(id),
    filename          VARCHAR(1000) NOT NULL,
    additions         INT NOT NULL DEFAULT 0,
    deletions         INT NOT NULL DEFAULT 0,
    status            VARCHAR(20),
    UNIQUE (pull_request_id, filename)
);
CREATE INDEX idx_changed_files_pull_request_id ON changed_files(pull_request_id);

-- PR_METRICS
CREATE TABLE pr_metrics (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id       UUID NOT NULL UNIQUE REFERENCES pull_requests(id),
    files_changed         INT,
    lines_added           INT,
    lines_deleted         INT,
    churn                 INT,
    commit_count          INT,
    test_files_changed    INT,
    is_sensitive_file     BOOLEAN NOT NULL DEFAULT false,
    computed_at           TIMESTAMPTZ
);

CREATE TABLE pr_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id UUID NOT NULL REFERENCES pull_requests(id),
    is_risky BOOLEAN NOT NULL DEFAULT false,
    reasons TEXT,
    label_window_days INT NOT NULL DEFAULT 60,
    labeled_at TIMESTAMPTZ,
    label_version INT NOT NULL DEFAULT 1,           -- 1 = original rule, 2 = refined rule (see routes/labels.py)
    window_complete BOOLEAN NOT NULL DEFAULT true,  -- false if the PR's window runs past the end of the data
    CONSTRAINT pr_labels_pr_version_key UNIQUE (pull_request_id, label_version)
);

ALTER TABLE users ADD COLUMN github_access_token TEXT;

-- GitHub's numeric user id: login matches on this because usernames can be renamed and reused
ALTER TABLE users ADD COLUMN github_user_id BIGINT UNIQUE;

-- Phase 11: GitHub's per-file diff ('patch') so the LLM can read what changed.
-- NULL when GitHub sends no patch (binary or very large files) or it was not fetched yet.
ALTER TABLE changed_files ADD COLUMN patch TEXT;

-- Phase 11: one stored LLM answer per PR, model, prompt version and RAG setting.
-- Ask once, save, reuse: experiments and the dashboard read from here, never re-ask.
CREATE TABLE llm_analyses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pull_request_id  UUID NOT NULL REFERENCES pull_requests(id),
    model            VARCHAR(100) NOT NULL,
    prompt_version   INT NOT NULL,
    use_rag          BOOLEAN NOT NULL DEFAULT false,
    risk_score       INT NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level       VARCHAR(10) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    result           JSONB NOT NULL,
    diff_truncated   BOOLEAN NOT NULL DEFAULT false,
    input_tokens     INT,
    output_tokens    INT,
    latency_ms       INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pull_request_id, model, prompt_version, use_rag)
);
CREATE INDEX idx_llm_analyses_pull_request_id ON llm_analyses(pull_request_id);

-- Phase 12 (RAG). Needs the pgvector extension, created once by a database admin:
--   CREATE EXTENSION vector;
-- One row per documentation file, pinned to the exact commit it was read from.
CREATE TABLE repo_documents (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id  UUID NOT NULL REFERENCES repositories(id),
    path           VARCHAR(500) NOT NULL,
    commit_sha     VARCHAR(40) NOT NULL,
    content        TEXT NOT NULL,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repository_id, path, commit_sha)
);

-- Pieces of those documents with their meaning vector (384 numbers per chunk).
CREATE TABLE document_chunks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      UUID NOT NULL REFERENCES repo_documents(id),
    chunk_index      INT NOT NULL,
    heading          TEXT,
    content          TEXT NOT NULL,
    embedding_model  VARCHAR(100) NOT NULL,
    embedding        vector(384) NOT NULL,
    UNIQUE (document_id, chunk_index, embedding_model)
);
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);

-- Phase 14: which doc chunks a RAG answer was given (NULL for non-RAG answers).
ALTER TABLE llm_analyses ADD COLUMN retrieved_chunks JSONB;
