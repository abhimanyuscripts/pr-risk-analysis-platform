# Backend

FastAPI backend: GitHub login, ingestion, metrics, risk labels, LLM/RAG analysis and the read-only
dashboard API (`routes/repos.py`, hybrid score in `scoring.py`). Every endpoint is under `/api`; outside
`/api` the same app serves the built React app (`STATIC_DIR`), so in Docker and on the live site the
browser talks to one address.

## Run

```
cd backend
source venv/bin/activate
python -m database.migrate       # once after pulling new code: brings the database schema up to date
uvicorn main:app --reload        # http://localhost:8000, API docs at /api/docs
```

Settings live in `backend/.env` (copy `.env.example`). With `npm run dev` in `frontend/`, open
http://localhost:5173; Vite forwards `/api` here.

## Who may read and write

- Read: a repository is visible to the account that added it, and to everyone without login if it is in
  `PUBLIC_REPOS` (the demo). Anything else answers 404.
- Write (ingest, patches, metrics, labels): only accounts in `ALLOWED_WRITERS`, and only on repositories
  they added. Empty = nobody, which is how the live site runs.
- `APP_ENV=production` refuses to start with weak or missing settings (`settings.py`).

## Upgrading from Phase 18 (once)

1. In `backend/.env`: `GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/callback`,
   `PUBLIC_REPOS=encode/httpx`, `ALLOWED_WRITERS=<your-github-username>`.
2. In the laptop's GitHub OAuth app, set the callback URL to `http://localhost:8000/api/auth/callback`.
3. `python -m database.migrate`, then `python scripts/add_label_evidence.py encode/httpx` (stores which
   later PR made each risky label risky; it changes no label and writes nothing if any label would change).

## Which requirements file?

- `requirements.txt`: everything, including the LLM / RAG / ML batch scripts (torch, transformers, ...).
  Use this on your laptop.
- `requirements-api.txt`: only what the API needs (no torch; a few hundred MB instead of several GB on Linux).
  Used by CI and the Docker image.
- `requirements-dev.txt`: the API list plus the test tools.

## Tests (Phase 17)

The tests need their own, empty PostgreSQL database, because they create and empty tables on every run.
Its name must end in `_test`; any other database is refused, so `pr_risk_dev` can never be touched.

One-time setup:

```
createdb -O pr_risk_app pr_risk_test
pip install -r requirements-dev.txt
```

and in `backend/.env` add the same URL as `DATABASE_URL` but with the test database name:

```
TEST_DATABASE_URL=postgresql+psycopg://pr_risk_app:<password>@localhost:5432/pr_risk_test
```

Then:

```
cd backend
pytest
```

The tests use fixed fake secrets and a fake GitHub, so they never call GitHub or the LLM.
GitHub Actions runs the same tests on every pull request (`.github/workflows/ci.yml`).
