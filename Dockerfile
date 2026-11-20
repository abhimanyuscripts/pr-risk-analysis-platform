# Phase 19: the whole site as ONE image, the same on the laptop (docker compose) and on Render.
# Stage 1 builds the React app; stage 2 is the FastAPI API, which also serves that build, so the
# browser sees a single address: pages at /, the API at /api.

FROM node:22-slim AS web
WORKDIR /web
# Install dependencies first, so a code change does not re-download them
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STATIC_DIR=/app/static

WORKDIR /app

# Only the light requirements (no torch): the LLM / RAG / ML batch scripts stay on the laptop.
COPY backend/requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY backend/ .
COPY --from=web /web/dist ./static

# Do not run as root inside the container
RUN useradd --create-home --uid 10001 app
USER 10001

EXPOSE 8000
# Bring the database schema up to date (safe to repeat), then serve. Render sets $PORT; the proxy
# headers make the app see the visitor's https address instead of the internal http one.
CMD ["sh", "-c", "python -m database.migrate && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
