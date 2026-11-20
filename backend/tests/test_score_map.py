"""GET /api/repos/{owner}/{repo}/score-map: the data behind the risk map (Phase 19)."""
from database.models import PRLabel
from tests.conftest import auth

MAP = "/api/repos/encode/httpx/score-map"


def points(client, user, query=""):
    body = client.get(MAP + query, headers=auth(user)).json()
    return body["reference_prs"], {p["number"]: p for p in body["points"]}


def test_every_reference_pr_with_its_hindsight(client, world):
    n, pts = points(client, world["a"])
    assert n == 4
    assert {k: p["hindsight"] for k, p in pts.items()} == {1: "no_fix", 2: "fix", 6: None, 7: "no_fix"}


def test_same_numbers_as_the_pr_list(client, world):
    _, pts = points(client, world["a"])
    items = client.get("/api/repos/encode/httpx/prs?sort=hybrid", headers=auth(world["a"])).json()["items"]
    for item in items:
        if item["hybrid"]:
            p = pts[item["number"]]
            assert (p["score"], p["size_percentile"], p["llm_percentile"]) == (
                item["hybrid"]["score"], item["hybrid"]["size_percentile"], item["hybrid"]["llm_percentile"])
            assert p["title"] == item["title"]


def test_an_incomplete_window_is_pending_not_no_fix(client, world, db):
    db.query(PRLabel).filter_by(pull_request_id=world["prs"][7].id, label_version=3).update({"window_complete": False})
    db.commit()
    assert points(client, world["a"])[1][7]["hindsight"] == "pending"


def test_another_label_version(client, world):
    _, pts = points(client, world["a"], "?label_version=2")
    assert {k: p["hindsight"] for k, p in pts.items()} == {1: "fix", 2: None, 6: None, 7: None}


def test_labels_never_move_the_points(client, world, db):
    before = points(client, world["a"])[1]
    db.query(PRLabel).update({"is_risky": True})
    db.commit()
    after = points(client, world["a"])[1]
    for k in before:
        assert (before[k]["size_percentile"], before[k]["llm_percentile"]) == (
            after[k]["size_percentile"], after[k]["llm_percentile"])


def test_a_repo_without_llm_answers_has_an_empty_map(client, world):
    body = client.get("/api/repos/acme/secret/score-map", headers=auth(world["b"])).json()
    assert body == {"reference_prs": 0, "points": []}


def test_private_maps_are_404(client, world):
    assert client.get(MAP, headers=auth(world["b"])).status_code == 404
    assert client.get(MAP).status_code == 404
