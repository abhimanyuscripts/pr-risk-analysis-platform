# Phase 18b: the API as a container. Only the light requirements (no torch): the LLM / RAG / ML
# batch scripts are not part of the running API and stay on the laptop.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first, so a code change does not re-download them
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY . .

# Do not run as root inside the container
RUN useradd --create-home --uid 10001 app
USER 10001

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
