#!/usr/bin/env bash
# Phase 18b: copy your local PostgreSQL data (pr_risk_dev) into the Docker database, once.
# Reads DATABASE_URL from backend/.env. Safe to run again: it replaces what is in the container.
# Needs pg_dump on the Mac (comes with the Homebrew PostgreSQL) and Docker running.
set -euo pipefail
cd "$(dirname "$0")/.."

line=$(grep -E '^DATABASE_URL=' backend/.env || true)
if [ -z "$line" ]; then
  echo "DATABASE_URL not found in backend/.env" >&2
  exit 1
fi
source_url=${line#DATABASE_URL=}
source_url=${source_url%\"}
source_url=${source_url#\"}
source_url=${source_url/+psycopg/} # pg_dump wants plain postgresql://

echo "Starting the database container..."
docker compose up -d --wait db

echo "Copying data (this can take a minute)..."
pg_dump --format=custom --no-owner --no-privileges "$source_url" \
  | docker compose exec -T db pg_restore --username=pr_risk_app --dbname=pr_risk_dev \
      --no-owner --no-privileges --clean --if-exists --exit-on-error

echo "Done. Rows in the container:"
docker compose exec -T db psql --username=pr_risk_app --dbname=pr_risk_dev --tuples-only --command \
  "SELECT 'pull_requests', count(*) FROM pull_requests UNION ALL SELECT 'llm_analyses', count(*) FROM llm_analyses UNION ALL SELECT 'document_chunks', count(*) FROM document_chunks;"
