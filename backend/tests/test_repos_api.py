"""Read-only dashboard API (16a): repo list, PR list (sort, filter, paging) and PR detail."""
import pytest

from tests.conftest import MODEL, auth, dt

PRS = "/api/repos/encode/httpx/prs"


def numbers(response):
    return [item["number"] for item in response.json()["items"]]


# ---- GET /repos ----

def test_repo_list_shows_only_your_repos_with_counts(client, world):
    body = client.get("/api/repos", headers=auth(world["a"])).json()
    assert [r["full_name"] for r in body] == ["encode/httpx"]
    r = body[0]
    # 6 PRs have at least one stored answer, whatever the model or RAG setting
    assert (r["pr_count"], r["llm_analyzed_count"], r["last_merged_at"][:10]) == (7, 6, "2024-06-01")
    other = client.get("/api/repos", headers=auth(world["b"])).json()
    assert [(x["full_name"], x["pr_count"], x["llm_analyzed_count"]) for x in other] == [("acme/secret", 1, 0)]


# ---- GET /repos/{owner}/{repo}/prs: order ----

@pytest.mark.parametrize("query, expected", [
    ("", [7, 5, 4, 3, 2, 1, 6]),                    # merge date, newest first; open PR (no date) last
    ("?desc=false", [1, 2, 3, 4, 5, 7, 6]),         # empty values stay last either way
    ("?sort=churn", [3, 7, 2, 4, 6, 1, 5]),         # ties broken by PR number; PR without metrics last
    ("?sort=llm_score", [7, 2, 6, 1, 5, 4, 3]),     # only the research model's RAG answer counts
])
def test_pr_order(client, world, query, expected):
    assert numbers(client.get(PRS + query, headers=auth(world["a"]))) == expected


# ---- filter and paging ----

@pytest.mark.parametrize("query, expected, total", [
    ("?risky=true", [3, 2], 2),
    ("?risky=false", [7, 4, 1], 3),                  # unlabelled PRs are in neither group
    ("?risky=true&label_version=2", [1], 1),
    ("?limit=3&offset=3", [3, 2, 1], 7),             # total counts every match, not the page
    ("?limit=3&offset=6", [6], 7),
    ("?limit=3&offset=7", [], 7),
])
def test_pr_filter_and_paging(client, world, query, expected, total):
    r = client.get(PRS + query, headers=auth(world["a"]))
    assert (numbers(r), r.json()["total"]) == (expected, total)


def test_pr_list_fields(client, world):
    items = {i["number"]: i for i in client.get(PRS, headers=auth(world["a"])).json()["items"]}
    assert items[2]["llm"] == {"risk_score": 70, "risk_level": "high", "use_rag": True}
    assert items[2]["label"] == {"version": 3, "is_risky": True, "window_complete": True}
    assert items[2]["churn"] == 50
    assert items[4]["label"]["window_complete"] is False   # too recent: the UI must say "pending"
    assert items[4]["llm"] is None                         # another model's answer is not shown
    assert items[3]["llm"] is None                         # a no-docs answer is not the RAG score
    assert (items[5]["churn"], items[5]["label"], items[5]["llm"]) == (None, None, None)
    assert (items[6]["merged_at"], items[6]["state"], items[6]["llm"]["risk_score"]) == (None, "open", 55)


# ---- access control and bad input ----

def test_other_users_repo_is_404_not_403(client, world):
    assert client.get(PRS, headers=auth(world["b"])).status_code == 404
    assert client.get("/api/repos/acme/secret/prs", headers=auth(world["a"])).status_code == 404
    assert client.get("/api/repos/nope/nope/prs", headers=auth(world["a"])).status_code == 404


def test_visitors_see_no_private_repo(client, world):
    """Without PUBLIC_REPOS nothing is public: a visitor gets an empty list and 404s, not 401s,
    so the API does not even confirm that a private repository exists."""
    assert client.get("/api/repos").json() == []
    for path in (PRS, PRS + "/2", "/api/repos/encode/httpx/score-map"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("query", ["?limit=0", "?limit=201", "?offset=-1", "?sort=bogus"])
def test_bad_query_values_are_422(client, world, query):
    assert client.get(PRS + query, headers=auth(world["a"])).status_code == 422


# ---- GET /repos/{owner}/{repo}/prs/{number} ----

@pytest.fixture
def detailed(world, seed, db):
    """Give PR 2 a description, reasons, an old-prompt answer, a full RAG answer and three files."""
    p2 = world["prs"][2]
    p2.description, p2.base_branch = "Adds gzip", "master"
    from database.models import LLMAnalysis, PRLabel
    db.query(LLMAnalysis).filter_by(pull_request_id=p2.id, use_rag=True).update({
        "result": {"summary": "Adds decoding", "tests_included": True,
                   "concerns": [{"category": "testing", "file": "httpx/_decoders.py", "explanation": "brotli untested"}]},
        "retrieved_chunks": [{"chunk_id": "c1", "heading": "Advanced > Compression", "distance": 0.41}],
        "diff_truncated": True,
    })
    db.query(PRLabel).filter_by(pull_request_id=p2.id).update({"reasons": "fix in #9 touched httpx/_decoders.py"})
    seed.label(p2, 2, False)
    seed.llm(p2, 5, prompt_version=0)
    seed.file(p2, "docs/a.md", 1, 0)
    seed.file(p2, "httpx/_decoders.py", 40, 10, patch="@@ ...")
    seed.file(p2, "tests/t.py", 5, 0, patch="@@")
    db.commit()
    return world


def test_detail_basics(client, detailed):
    d = client.get(PRS + "/2", headers=auth(detailed["a"])).json()
    assert (d["number"], d["title"], d["description"], d["base_branch"]) == (2, "PR 2", "Adds gzip", "master")
    assert d["github_url"] == "https://github.com/encode/httpx/pull/2"
    assert (d["metrics"]["churn"], d["metrics"]["files_changed"], d["metrics"]["is_sensitive_file"]) == (50, 2, False)


def test_detail_labels_newest_version_first_with_reasons(client, detailed):
    d = client.get(PRS + "/2", headers=auth(detailed["a"])).json()
    assert [(l["version"], l["is_risky"], l["reasons"]) for l in d["labels"]] == [
        (3, True, "fix in #9 touched httpx/_decoders.py"), (2, False, None)]


def test_detail_llm_answers_research_rag_first(client, detailed):
    d = client.get(PRS + "/2", headers=auth(detailed["a"])).json()
    assert [(a["prompt_version"], a["use_rag"], a["risk_score"]) for a in d["llm_analyses"]] == [
        (1, True, 70), (1, False, 30), (0, True, 5)]
    main = d["llm_analyses"][0]
    assert main["model"] == MODEL
    assert main["summary"] == "Adds decoding"
    assert main["concerns"] == [{"category": "testing", "file": "httpx/_decoders.py", "explanation": "brotli untested"}]
    assert (main["tests_included"], main["diff_truncated"]) == (True, True)
    assert main["retrieved_docs"] == [{"heading": "Advanced > Compression", "distance": 0.41}]
    empty = d["llm_analyses"][2]
    assert (empty["summary"], empty["concerns"], empty["retrieved_docs"]) == ("", [], [])


def test_detail_files_biggest_first_without_diff_text(client, detailed):
    d = client.get(PRS + "/2", headers=auth(detailed["a"])).json()
    assert [(f["filename"], f["has_diff"]) for f in d["files"]] == [
        ("httpx/_decoders.py", True), ("tests/t.py", True), ("docs/a.md", False)]
    assert all("patch" not in f for f in d["files"])


def test_detail_of_a_pr_with_nothing_stored(client, world):
    d = client.get(PRS + "/5", headers=auth(world["a"])).json()
    assert (d["metrics"], d["labels"], d["llm_analyses"], d["files"], d["hybrid"]) == (None, [], [], [], None)


def test_detail_errors(client, world):
    assert client.get(PRS + "/999", headers=auth(world["a"])).status_code == 404
    assert client.get(PRS + "/2", headers=auth(world["b"])).status_code == 404
    assert client.get(PRS + "/abc", headers=auth(world["a"])).status_code == 422


def test_extra_rows_never_duplicate_a_pr_in_the_list(client, detailed):
    assert numbers(client.get(PRS, headers=auth(detailed["a"]))).count(2) == 1
