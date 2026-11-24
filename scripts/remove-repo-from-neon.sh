#!/usr/bin/env bash
# Remove ONE repository and everything stored for it from the hosted database (Neon).
#   scripts/remove-repo-from-neon.sh owner/name                dry run: shows what would go, changes nothing
#   CONFIRM=yes scripts/remove-repo-from-neon.sh owner/name    removes it
# Asks for the Neon connection string (input hidden) unless NEON_DATABASE_URL is set.
# Only that repository's rows are touched: its pull requests, commits, changed files, metrics, labels,
# LLM answers, documents and document chunks. Users and every other repository stay as they are.
# Everything runs in one transaction: if any row count does not add up, nothing is changed.
# Your laptop's database is not touched, so scripts/copy-db-to-neon.sh can put the repository back.
# Needs psql (Homebrew PostgreSQL).
set -euo pipefail

repo=${1:-}
if [[ ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "Usage: scripts/remove-repo-from-neon.sh owner/name" >&2
  exit 1
fi
if [ "$(printf '%s' "$repo" | tr '[:upper:]' '[:lower:]')" = "encode/httpx" ]; then
  echo "encode/httpx is the study the live site shows. This script will not remove it." >&2
  exit 1
fi

target=${NEON_DATABASE_URL:-}
if [ -z "$target" ]; then
  read -rsp "Paste the Neon connection string (it is not shown or saved): " target
  echo
fi
target=${target/+psycopg/} # psql wants plain postgresql://

confirm=false
[ "${CONFIRM:-}" = "yes" ] && confirm=true

psql "$target" -X -q -v ON_ERROR_STOP=1 -v repo="$repo" -v confirm="$confirm" <<'SQL'
BEGIN;

CREATE TEMP TABLE target_repo ON COMMIT DROP AS
  SELECT id FROM repositories WHERE lower(full_name) = lower(:'repo');
DO $$ BEGIN
  IF (SELECT count(*) FROM target_repo) <> 1 THEN
    RAISE EXCEPTION 'No repository with that name in this database. Nothing was changed.';
  END IF;
END $$;
CREATE TEMP TABLE target_prs ON COMMIT DROP AS
  SELECT id FROM pull_requests WHERE repository_id IN (SELECT id FROM target_repo);
CREATE TEMP TABLE target_docs ON COMMIT DROP AS
  SELECT id FROM repo_documents WHERE repository_id IN (SELECT id FROM target_repo);

-- Every table's total before, and how many of its rows belong to this repository.
CREATE TEMP TABLE plan (step int, tbl text, rows_of_repo bigint, before bigint, after bigint) ON COMMIT DROP;
INSERT INTO plan (step, tbl, rows_of_repo, before) VALUES
  (1, 'document_chunks', (SELECT count(*) FROM document_chunks WHERE document_id IN (SELECT id FROM target_docs)), (SELECT count(*) FROM document_chunks)),
  (2, 'repo_documents',  (SELECT count(*) FROM target_docs),                                                    (SELECT count(*) FROM repo_documents)),
  (3, 'llm_analyses',    (SELECT count(*) FROM llm_analyses  WHERE pull_request_id IN (SELECT id FROM target_prs)), (SELECT count(*) FROM llm_analyses)),
  (4, 'pr_labels',       (SELECT count(*) FROM pr_labels     WHERE pull_request_id IN (SELECT id FROM target_prs)), (SELECT count(*) FROM pr_labels)),
  (5, 'pr_metrics',      (SELECT count(*) FROM pr_metrics    WHERE pull_request_id IN (SELECT id FROM target_prs)), (SELECT count(*) FROM pr_metrics)),
  (6, 'changed_files',   (SELECT count(*) FROM changed_files WHERE pull_request_id IN (SELECT id FROM target_prs)), (SELECT count(*) FROM changed_files)),
  (7, 'commits',         (SELECT count(*) FROM commits       WHERE pull_request_id IN (SELECT id FROM target_prs)), (SELECT count(*) FROM commits)),
  (8, 'pull_requests',   (SELECT count(*) FROM target_prs),                                                    (SELECT count(*) FROM pull_requests)),
  (9, 'repositories',    1,                                                                                     (SELECT count(*) FROM repositories)),
  (10, 'users',          0,                                                                                     (SELECT count(*) FROM users));

-- Children first, so no foreign key is ever left pointing at a removed row.
DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM target_docs);
DELETE FROM repo_documents  WHERE id IN (SELECT id FROM target_docs);
DELETE FROM llm_analyses    WHERE pull_request_id IN (SELECT id FROM target_prs);
DELETE FROM pr_labels       WHERE pull_request_id IN (SELECT id FROM target_prs);
DELETE FROM pr_metrics      WHERE pull_request_id IN (SELECT id FROM target_prs);
DELETE FROM changed_files   WHERE pull_request_id IN (SELECT id FROM target_prs);
DELETE FROM commits         WHERE pull_request_id IN (SELECT id FROM target_prs);
DELETE FROM pull_requests   WHERE id IN (SELECT id FROM target_prs);
DELETE FROM repositories    WHERE id IN (SELECT id FROM target_repo);

UPDATE plan SET after = CASE tbl
  WHEN 'document_chunks' THEN (SELECT count(*) FROM document_chunks)
  WHEN 'repo_documents'  THEN (SELECT count(*) FROM repo_documents)
  WHEN 'llm_analyses'    THEN (SELECT count(*) FROM llm_analyses)
  WHEN 'pr_labels'       THEN (SELECT count(*) FROM pr_labels)
  WHEN 'pr_metrics'      THEN (SELECT count(*) FROM pr_metrics)
  WHEN 'changed_files'   THEN (SELECT count(*) FROM changed_files)
  WHEN 'commits'         THEN (SELECT count(*) FROM commits)
  WHEN 'pull_requests'   THEN (SELECT count(*) FROM pull_requests)
  WHEN 'repositories'    THEN (SELECT count(*) FROM repositories)
  WHEN 'users'           THEN (SELECT count(*) FROM users)
END;

\echo
\echo 'Rows of' :repo 'and the table totals before and after:'
SELECT tbl AS "table", rows_of_repo AS "rows of this repository", before, after FROM plan ORDER BY step;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM plan WHERE after IS DISTINCT FROM before - rows_of_repo) THEN
    RAISE EXCEPTION 'Row counts do not add up. Nothing was changed.';
  END IF;
END $$;

\if :confirm
COMMIT;
\echo 'Removed. The counts above are now in the database.'
\else
ROLLBACK;
\echo 'Dry run: nothing was changed. Run again with CONFIRM=yes to remove it.'
\endif
SQL
