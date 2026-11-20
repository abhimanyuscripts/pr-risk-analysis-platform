"""Login and access control: the Bearer token, CORS, and the GitHub login redirect (16a, 16c)."""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import main
import routes.auth as auth_routes
from auth.jwt_handler import decode_access_token
from database.models import User
from tests.conftest import auth


@pytest.fixture
def alice(seed, db):
    u = seed.user("alice", 1)
    db.commit()
    return u


# ---- Bearer token ----

def test_no_header_is_401(client):
    r = client.get("/api/users/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing or invalid authorization header"


def test_garbage_token_is_401(client):
    r = client.get("/api/users/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or expired token"


def test_wrong_scheme_is_401(client, alice):
    token = auth(alice)["Authorization"].split()[1]
    assert client.get("/api/users/me", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_valid_token_returns_the_user(client, alice):
    r = client.get("/api/users/me", headers=auth(alice))
    assert r.status_code == 200
    assert r.json() == {"github_username": "alice", "user_id": str(alice.id)}


def test_lowercase_bearer_is_accepted(client, alice):
    token = auth(alice)["Authorization"].split()[1]
    assert client.get("/api/users/me", headers={"Authorization": f"bearer {token}"}).status_code == 200


def test_router_level_protection_still_applies(client):
    assert client.post("/api/metrics/compute/a/b").status_code == 401


def test_swagger_gets_an_authorize_button(client):
    spec = main.app.openapi()
    assert spec["components"]["securitySchemes"]["HTTPBearer"] == {"type": "http", "scheme": "bearer"}
    assert spec["paths"]["/api/users/me"]["get"].get("security")


# ---- CORS ----

PREFLIGHT = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://localhost:3000"])
def test_cors_allows_the_frontend(client, origin):
    r = client.options("/api/users/me", headers={**PREFLIGHT, "Origin": origin})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin


def test_cors_refuses_other_sites(client):
    r = client.options("/api/users/me", headers={**PREFLIGHT, "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


# ---- GitHub login (GitHub itself is replaced by a fake) ----

class _FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


class _FakeGitHub:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):  # code -> GitHub access token
        return _FakeResponse(200, {"access_token": "gho_fake"})

    async def get(self, *args, **kwargs):  # token -> GitHub profile
        return _FakeResponse(200, {"id": 4242, "login": "alice", "email": None})


@pytest.fixture
def login_client(monkeypatch):
    monkeypatch.setattr(auth_routes.httpx, "AsyncClient", _FakeGitHub)
    return TestClient(main.app, follow_redirects=False)


def _state(response) -> str:
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def test_app_login_goes_to_github_and_marks_the_app(login_client):
    r = login_client.get("/api/auth/login?app=true")
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://github.com/login/oauth/authorize")
    cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith("oauth_state=") for c in cookies)
    assert any(c.startswith("login_target=app") and "HttpOnly" in c for c in cookies)


def test_app_login_returns_to_the_app_with_the_token_after_hash(login_client, db):
    state = _state(login_client.get("/api/auth/login?app=true"))
    r = login_client.get(f"/api/auth/callback?code=abc&state={state}")
    location = r.headers["location"]
    assert r.status_code == 307
    assert location.startswith("http://localhost:5173/auth/done#token=")
    assert "?" not in location  # the token is never in the query string
    user = db.query(User).filter_by(github_user_id=4242).one()
    assert decode_access_token(location.split("#token=", 1)[1]) == str(user.id)
    cleared = r.headers.get_list("set-cookie")
    assert any(c.startswith(("oauth_state=\"\"", "oauth_state=;")) for c in cleared)
    assert any(c.startswith(("login_target=\"\"", "login_target=;")) for c in cleared)


def test_plain_login_still_returns_json_for_swagger(login_client):
    r = login_client.get("/api/auth/login")
    assert not any(c.startswith("login_target=app") for c in r.headers.get_list("set-cookie"))
    r = login_client.get(f"/api/auth/callback?code=abc&state={_state(r)}")
    assert r.status_code == 200
    assert r.json()["github_username"] == "alice"
    assert decode_access_token(r.json()["access_token"])


def test_wrong_state_is_refused(login_client):
    login_client.get("/api/auth/login")
    assert login_client.get("/api/auth/callback?code=abc&state=wrong").status_code == 400
