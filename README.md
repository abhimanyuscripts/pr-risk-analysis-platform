# PR Risk Analysis Platform

AI-powered Pull Request risk analysis platform combining traditional software-engineering metrics, machine learning, and a RAG-grounded LLM into an explainable hybrid risk assessment.

**Status:** backend, research pipeline, React dashboard, tests and CI built (Phases 0–18 of 21).

## Research Question

Does combining traditional PR metrics, ML-based risk prediction, and RAG-enhanced LLM semantic analysis produce a more accurate and more informative PR risk assessment than using each approach individually?

## Tech Stack

- **Frontend:** React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** PostgreSQL + pgvector
- **ML:** scikit-learn, XGBoost, SHAP
- **AI:** LLM API with structured/JSON output, RAG (retrieval-augmented generation)

## Team

Final-year B.Tech project — 4-member team.

## Run it with Docker (simplest)

Needs Docker Desktop and a filled-in `backend/.env` (copy `backend/.env.example`: GitHub OAuth app, JWT and encryption keys).

```
docker compose up --build     # first build takes a few minutes
```

Then open http://localhost:5173 and log in with GitHub. The API is on http://localhost:8000 (docs at /docs).

The container database starts empty. To copy your local data into it once (needs `pg_dump`, which comes with PostgreSQL):

```
scripts/copy-db-to-docker.sh
```

Stop the local `uvicorn` (port 8000) and `npm run dev` (port 5173) before starting the containers. The database
container listens on port 5433, so it does not clash with a local PostgreSQL on 5432. `docker compose down` stops
everything; the data stays in the `pgdata` volume (`docker compose down -v` deletes it).

## Run it without Docker

See `backend/README.md` and `frontend/README.md`.