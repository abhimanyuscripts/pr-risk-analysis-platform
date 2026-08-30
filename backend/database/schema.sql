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