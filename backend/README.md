# Backend

FastAPI backend: GitHub login, ingestion, metrics, risk labels, LLM/RAG analysis and the read-only
dashboard API (`routes/repos.py`, hybrid score in `scoring.py`).

## Run

```
cd backend
source venv/bin/activate
uvicorn main:app --reload        # http://localhost:8000, API docs at /docs
```

Settings live in `backend/.env` (copy `.env.example`).

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
