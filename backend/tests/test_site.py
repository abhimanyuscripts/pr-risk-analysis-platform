"""One website (Phase 19): the API under /api, the React build everywhere else, the health check
and the checks that stop an unsafe production start."""
import os
import subprocess
import sys

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.exc import OperationalError

import main
from database.connection import get_db
from settings import BACKEND_DIR, production_problems


# ---- health ----

def test_health_checks_the_database(client):
    r = client.get("/api/health")
    assert (r.status_code, r.json()) == (200, {"status": "ok", "database": "connected"})


def test_health_is_503_when_the_database_is_down(client):
    class Broken:
        def execute(self, *args):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    main.app.dependency_overrides[get_db] = lambda: Broken()
    try:
        r = client.get("/api/health")
    finally:
        main.app.dependency_overrides.clear()
    assert (r.status_code, r.json()["database"]) == (503, "unreachable")


def test_api_docs_live_under_api(client):
    assert client.get("/api/docs").status_code == 200
    assert "/api/repos" in client.get("/api/openapi.json").json()["paths"]


def test_unknown_api_paths_are_json_404s(client):
    r = client.get("/api/does-not-exist")
    assert (r.status_code, r.json()) == (404, {"detail": "Not found"})


def test_security_headers_on_api_answers(client):
    h = client.get("/api/health").headers
    assert (h["x-content-type-options"], h["x-frame-options"]) == ("nosniff", "DENY")
    assert "strict-transport-security" not in h  # only in production (https)


# ---- the React build ----

@pytest.fixture
def build(tmp_path, monkeypatch):
    site = tmp_path / "dist"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html><div id=root></div>")
    (site / "assets" / "index-abc123.js").write_text("console.log('app')")
    (site / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    monkeypatch.setenv("STATIC_DIR", str(site))
    return site


@pytest.mark.parametrize("path", ["/", "/repos", "/repos/encode/httpx/prs/3394", "/login", "/no/such/page"])
def test_app_pages_get_index_html(client, build, path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.text.startswith("<!doctype html>")
    assert r.headers["cache-control"] == "no-cache"  # a new deploy shows up on the next visit
    csp = r.headers["content-security-policy"]
    assert "script-src 'self';" in csp            # no inline or third-party scripts
    assert "font-src 'self' data:" in csp         # Vite inlines the smallest font files as data: URLs


def test_hashed_assets_are_cached_for_a_year(client, build):
    r = client.get("/assets/index-abc123.js")
    assert r.text == "console.log('app')"
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "javascript" in r.headers["content-type"]


def test_other_files_are_served_with_a_short_cache(client, build):
    r = client.get("/favicon.svg")
    assert (r.status_code, r.headers["cache-control"]) == (200, "public, max-age=3600")


def test_a_missing_asset_is_404_not_the_page(client, build):
    """Old tabs ask for the previous deploy's files; HTML in place of a script would break them."""
    r = client.get("/assets/index-old999.js")
    assert r.status_code == 404
    assert "<!doctype" not in r.text


@pytest.mark.parametrize("path", ["/..%2fsecret.txt", "/assets/..%2f..%2fsecret.txt", "/%2e%2e/secret.txt"])
def test_files_outside_the_build_are_never_served(client, build, path):
    assert "TOP SECRET" not in client.get(path).text


def test_head_requests_work(client, build):
    assert client.head("/").status_code == 200


def test_without_a_build_the_root_points_to_the_docs(client):
    r = client.get("/")
    assert r.json()["api_docs"] == "/api/docs"
    assert client.get("/repos").status_code == 404


# ---- production settings ----

GOOD = {
    "APP_ENV": "production",
    "DATABASE_URL": "postgresql+psycopg://u:p@db.example/neondb?sslmode=require",
    "JWT_SECRET_KEY": "k" * 48,
    "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "GITHUB_CLIENT_ID": "id",
    "GITHUB_CLIENT_SECRET": "secret",
    "GITHUB_REDIRECT_URI": "https://pr-risk.example/api/auth/callback",
    "FRONTEND_URL": "https://pr-risk.example",
}


def test_good_production_settings_have_no_problems(monkeypatch):
    for k, v in GOOD.items():
        monkeypatch.setenv(k, v)
    assert production_problems() == []


@pytest.mark.parametrize("name, value, problem", [
    ("JWT_SECRET_KEY", "test-jwt-secret", "JWT_SECRET_KEY"),
    ("JWT_SECRET_KEY", "short", "JWT_SECRET_KEY"),
    ("TOKEN_ENCRYPTION_KEY", "not-a-key", "TOKEN_ENCRYPTION_KEY"),
    ("GITHUB_REDIRECT_URI", "http://localhost:8000/api/auth/callback", "GITHUB_REDIRECT_URI"),
    ("GITHUB_REDIRECT_URI", "https://pr-risk.example/auth/callback", "GITHUB_REDIRECT_URI"),
    ("FRONTEND_URL", "http://localhost:5173", "FRONTEND_URL"),
    ("GITHUB_CLIENT_SECRET", "", "GITHUB_CLIENT_SECRET"),
    ("DATABASE_URL", "", "DATABASE_URL"),
])
def test_each_unsafe_setting_is_named(monkeypatch, name, value, problem):
    for k, v in {**GOOD, name: value}.items():
        monkeypatch.setenv(k, v)
    problems = production_problems()
    assert len(problems) == 1 and problem in problems[0]


def _start(env: dict) -> subprocess.CompletedProcess:
    """Import the app in a fresh Python, as uvicorn would, with only these settings."""
    clean = {k: v for k, v in os.environ.items() if k not in GOOD}
    return subprocess.run([sys.executable, "-c", "import main"], cwd=BACKEND_DIR, env={**clean, **env},
                          capture_output=True, text=True, timeout=60)


def test_production_refuses_to_start_with_laptop_secrets():
    r = _start({**GOOD, "JWT_SECRET_KEY": "test-jwt-secret"})
    assert r.returncode != 0
    assert "Not safe to start in production" in r.stderr and "JWT_SECRET_KEY" in r.stderr


def test_production_starts_with_good_settings():
    r = _start(GOOD)
    assert r.returncode == 0, r.stderr


# ---- database address ----

@pytest.mark.parametrize("given, used", [
    ("postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require", "postgresql+psycopg://u:p@ep-x.neon.tech/neondb?sslmode=require"),
    ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    (None, None),
])
def test_host_database_urls_get_the_installed_driver(given, used):
    from database.connection import sqlalchemy_url
    assert sqlalchemy_url(given) == used
