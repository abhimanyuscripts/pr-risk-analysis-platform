"""Who may read and who may write (Phase 19): the public demo and the ALLOWED_WRITERS lock."""
import pytest

import routes.github as github_routes
from tests.conftest import auth

PRS = "/api/repos/encode/httpx/prs"


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("PUBLIC_REPOS", "encode/httpx")


# ---- reading: the public demo ----

def test_visitor_reads_the_public_demo_without_logging_in(client, world, demo):
    repos = client.get("/api/repos").json()
    assert [(r["full_name"], r["is_public"], r["is_owner"]) for r in repos] == [("encode/httpx", True, False)]
    assert client.get(PRS).json()["total"] == 7
    assert client.get(PRS + "/2").json()["number"] == 2
    assert client.get("/api/repos/encode/httpx/score-map").status_code == 200


def test_public_repo_names_ignore_case(client, world, monkeypatch):
    monkeypatch.setenv("PUBLIC_REPOS", " Encode/HTTPX , other/thing")
    assert [r["full_name"] for r in client.get("/api/repos").json()] == ["encode/httpx"]


def test_private_repos_stay_private_with_a_demo_on(client, world, demo):
    assert client.get("/api/repos/acme/secret/prs").status_code == 404                        # visitor
    assert client.get("/api/repos/acme/secret/prs", headers=auth(world["a"])).status_code == 404  # another user
    assert client.get("/api/repos/acme/secret/score-map", headers=auth(world["a"])).status_code == 404
    mine = client.get("/api/repos", headers=auth(world["b"])).json()
    assert [(r["full_name"], r["is_public"], r["is_owner"]) for r in mine] == [
        ("acme/secret", False, True), ("encode/httpx", True, False)]


def test_owner_of_the_demo_sees_it_once(client, world, demo):
    repos = client.get("/api/repos", headers=auth(world["a"])).json()
    assert [(r["full_name"], r["is_public"], r["is_owner"]) for r in repos] == [("encode/httpx", True, True)]


def test_an_expired_token_is_refused_even_on_public_pages(client, world, demo):
    """A visitor with no token is welcome; a token that is sent must be valid, so the app learns that
    it expired, forgets it and asks again without it."""
    bad = {"Authorization": "Bearer expired"}
    assert client.get(PRS, headers=bad).status_code == 401
    assert client.get("/api/repos", headers=bad).status_code == 401
    assert client.get(PRS).status_code == 200


# ---- writing: only ALLOWED_WRITERS, only on their own repositories ----

WRITES = ["/api/metrics/compute/encode/httpx", "/api/labels/compute/encode/httpx?version=3"]


@pytest.mark.parametrize("path", WRITES)
def test_writes_need_a_login(client, world, path):
    assert client.post(path).status_code == 401


@pytest.mark.parametrize("path", WRITES)
def test_logged_in_but_not_a_writer_is_403(client, world, path):
    r = client.post(path, headers=auth(world["b"]))  # bob is not in ALLOWED_WRITERS
    assert r.status_code == 403
    assert "ALLOWED_WRITERS" in r.json()["detail"]


@pytest.mark.parametrize("path", WRITES)
def test_nobody_writes_when_the_list_is_empty(client, world, monkeypatch, path):
    monkeypatch.setenv("ALLOWED_WRITERS", "")
    assert client.post(path, headers=auth(world["a"])).status_code == 403


def test_writer_names_ignore_case(client, world, monkeypatch):
    monkeypatch.setenv("ALLOWED_WRITERS", "ALICE")
    assert client.post(WRITES[0], headers=auth(world["a"])).status_code == 200


def test_a_writer_recomputes_their_own_repo(client, world):
    r = client.post(WRITES[0], headers=auth(world["a"]))
    assert r.status_code == 200
    assert r.json() == {"repository": "encode/httpx", "metrics_computed": 7}


@pytest.mark.parametrize("path", WRITES)
def test_a_writer_cannot_touch_another_accounts_repo(client, world, monkeypatch, path):
    monkeypatch.setenv("ALLOWED_WRITERS", "alice,bob")
    assert client.post(path, headers=auth(world["b"])).status_code == 404


class _FakeGitHub:
    """Stands in for GitHub. Records every URL so a test can prove what was (not) requested."""
    calls: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        _FakeGitHub.calls.append(url)

        class R:
            status_code = 200

            @staticmethod
            def json():
                return {"id": 101, "name": "httpx", "full_name": "encode/httpx", "owner": {"login": "encode"}}
        return R()


@pytest.fixture
def fake_github(monkeypatch):
    _FakeGitHub.calls = []
    monkeypatch.setattr(github_routes.httpx, "AsyncClient", _FakeGitHub)
    return _FakeGitHub


def test_ingest_by_a_non_writer_never_reaches_github(client, world, fake_github):
    assert client.post("/api/github/repos/encode/httpx/ingest", headers=auth(world["b"])).status_code == 403
    assert fake_github.calls == []


def test_ingest_of_a_repo_another_account_added_is_refused_before_downloading(client, world, fake_github, monkeypatch):
    monkeypatch.setenv("ALLOWED_WRITERS", "bob")
    r = client.post("/api/github/repos/encode/httpx/ingest", headers=auth(world["b"]))
    assert r.status_code == 409
    assert fake_github.calls == ["https://api.github.com/repos/encode/httpx"]  # no PR pages fetched


def test_patches_by_a_non_owner_are_404(client, world, monkeypatch):
    monkeypatch.setenv("ALLOWED_WRITERS", "bob")
    r = client.post("/api/github/repos/encode/httpx/patches?merged_since=2024-01-01", headers=auth(world["b"]))
    assert r.status_code == 404
