#!/usr/bin/env bash
# Phase 19: copy your local PostgreSQL data (pr_risk_dev) into the hosted database (Neon) for the live site.
#   scripts/copy-db-to-neon.sh                 asks for the Neon connection string (input hidden)
#   REPLACE=yes scripts/copy-db-to-neon.sh     replaces everything already in that database
# What goes up: every table's data EXCEPT the users table. Of users, only the account(s) that added a
# repository are copied, and only their id, GitHub id, username and sign-up time: no email, no GitHub
# token (it was encrypted with your laptop's key and is useless there anyway; logging in on the site
# stores a fresh one). Needs pg_dump, pg_restore and psql (Homebrew PostgreSQL).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "${SOURCE_DATABASE_URL:-}" ]; then
  source_url=$SOURCE_DATABASE_URL
else
  line=$(grep -E '^DATABASE_URL=' backend/.env || true)
  if [ -z "$line" ]; then
    echo "DATABASE_URL not found in backend/.env" >&2
    exit 1
  fi
  source_url=${line#DATABASE_URL=}
  source_url=${source_url%\"}
  source_url=${source_url#\"}
fi
source_url=${source_url/+psycopg/} # the PostgreSQL tools want plain postgresql://

target=${NEON_DATABASE_URL:-}
if [ -z "$target" ]; then
  read -rsp "Paste the Neon connection string (it is not shown or saved): " target
  echo
fi
target=${target/+psycopg/}

tables=$(psql "$target" -X -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
if [ "$tables" != "0" ]; then
  if [ "${REPLACE:-}" != "yes" ]; then
    echo "That database already has $tables tables. Run again with REPLACE=yes to replace them." >&2
    exit 1
  fi
  echo "Emptying the target database..."
  psql "$target" -X -q -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
fi

# The RAG tables need pgvector. Neon lets the database owner turn it on; say so clearly if it cannot.
if ! psql "$target" -X -q -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector" 2>"${TMPDIR:-/tmp}/pgvector.err"; then
  cat "${TMPDIR:-/tmp}/pgvector.err" >&2
  echo "Could not turn on the pgvector extension in the target database (needed for document_chunks)." >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "Reading the local database..."
pg_dump --format=custom --no-owner --no-privileges --exclude-table-data=users "$source_url" > "$work/data.dump"
psql "$source_url" -X -At -v ON_ERROR_STOP=1 -c \
  "COPY (SELECT id, github_user_id, github_username, created_at FROM users
         WHERE id IN (SELECT added_by FROM repositories)) TO STDOUT WITH CSV" > "$work/owners.csv"

# Comments on the pgvector extension and the public schema need a superuser, which a hosted
# database does not give you; they carry no data, so they are left out.
pg_restore --list "$work/data.dump" | grep -v -E 'COMMENT - (EXTENSION|SCHEMA)' > "$work/items.list"

echo "Writing to the hosted database (a few minutes on a slow connection)..."
restore() {
  pg_restore --no-owner --no-privileges --exit-on-error --use-list="$work/items.list" --dbname="$target" "$@" "$work/data.dump"
}
restore --section=pre-data # tables, the pgvector extension
psql "$target" -X -q -v ON_ERROR_STOP=1 \
  -c "\\copy users (id, github_user_id, github_username, created_at) FROM '$work/owners.csv' WITH CSV"
restore --section=data
restore --section=post-data # indexes and foreign keys, checked against the copied rows

echo "Done. Rows on the hosted database:"
psql "$target" -X -At -F ' ' -c \
  "SELECT 'users', count(*) FROM users UNION ALL SELECT 'repositories', count(*) FROM repositories
   UNION ALL SELECT 'pull_requests', count(*) FROM pull_requests UNION ALL SELECT 'pr_labels', count(*) FROM pr_labels
   UNION ALL SELECT 'llm_analyses', count(*) FROM llm_analyses UNION ALL SELECT 'document_chunks', count(*) FROM document_chunks;"
