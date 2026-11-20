# PR Risk Analysis Platform

AI-powered Pull Request risk analysis platform combining traditional software-engineering metrics, machine learning, and a RAG-grounded LLM into an explainable hybrid risk assessment.

**Status:** Phases 0–19 of 21 done: backend, research pipeline, website, tests, CI, Docker and the live site.

**Live:** https://pr-risk.onrender.com (the encode/httpx demo opens without logging in; on the free plan the
first visit after a quiet spell takes about a minute).

## Research Question

Does combining traditional PR metrics, ML-based risk prediction, and RAG-enhanced LLM semantic analysis produce a more accurate and more informative PR risk assessment than using each approach individually?

## Tech Stack

- **Frontend:** React, TypeScript, Tailwind CSS, GSAP (scroll story on the start page)
- **Backend:** Python, FastAPI, SQLAlchemy (also serves the built frontend: one website)
- **Database:** PostgreSQL + pgvector
- **ML:** scikit-learn
- **AI:** Gemini with structured JSON output, RAG over the project's own documentation
- **Delivery:** Docker, GitHub Actions; Render + Neon for the live site

## Team

Final-year B.Tech project — 4-member team.

## Run it with Docker (simplest)

Needs Docker Desktop and a filled-in `backend/.env` (copy `backend/.env.example`: GitHub OAuth app, JWT and encryption keys).

```
docker compose up --build     # first build takes a few minutes
```

Then open http://localhost:8000: the website and the API (`/api`, Swagger at `/api/docs`) from one container,
the same image the live site runs.

The container database starts empty. To copy your local data into it once (needs `pg_dump`, which comes with PostgreSQL):

```
scripts/copy-db-to-docker.sh
```

Stop the local `uvicorn` (port 8000) before starting the containers. The database container listens on port
5433, so it does not clash with a local PostgreSQL on 5432. `docker compose down` stops everything; the data
stays in the `pgdata` volume (`docker compose down -v` deletes it).

## Run it without Docker

See `backend/README.md` and `frontend/README.md`.

## Deploy

See [docs/DEPLOY.md](docs/DEPLOY.md): Neon for the database, Render for the website (`render.yaml`).
