"""Hybrid score (16b): the SQL in backend/scoring.py must give exactly Phase 15's numbers.

The reference implementation is research/hybrid_rules.py (pandas). Here both run on the same
random repo, with tied values and distracting answers that must not count.
"""
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.conftest import auth, dt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research"))
from hybrid_rules import pct_rank, rank_average  # noqa: E402

URL = "/repos/big/repo/prs"


@pytest.fixture
def random_repo(seed, db):
    rng = random.Random(7)
    user = seed.user("alice", 1)
    repo = seed.repo(user, "big", "repo", 303)
    reference = []
    for n in range(1, 151):
        pr = seed.pr(repo, n, dt(2023, 1, 1))
        churn = rng.choice([1, 2, 5, 10, 10, 23, 50, 120, 400]) if n % 13 else None  # ties; some without metrics
        if churn is not None:
            seed.metrics(pr, churn)
        kind = n % 7
        score = rng.choice([0, 5, 10, 10, 15, 20, 25, 40, 60, 75])
        if kind != 0:                       # 1 in 7 PRs has no answer at all
            seed.llm(pr, score, rag=(kind != 3))
        if kind == 5:                       # must NOT count: a no-docs answer and another model
            seed.llm(pr, 99, rag=False)
            seed.llm(pr, 99, model="other")
        if churn is not None and kind not in (0, 3):
            reference.append((n, churn, score))
    db.commit()
    ref = pd.DataFrame(reference, columns=["n", "churn", "score"])
    ref["want"] = rank_average(ref.churn.to_numpy(), ref.score.to_numpy()) * 100
    ref["want_size"] = pct_rank(ref.churn.to_numpy()) * 100
    ref["want_llm"] = pct_rank(ref.score.to_numpy()) * 100
    return user, ref


def all_items(client, user, query=""):
    items = []
    for offset in (0, 100):
        r = client.get(f"{URL}?sort=hybrid&limit=100&offset={offset}{query}", headers=auth(user))
        items += r.json()["items"]
    return items


def test_only_reference_prs_get_a_hybrid(client, random_repo):
    user, ref = random_repo
    items = all_items(client, user)
    assert len(items) == 150
    assert {i["number"] for i in items if i["hybrid"]} == set(ref.n)
    assert all(i["hybrid"]["reference_prs"] == len(ref) for i in items if i["hybrid"])


def test_hybrid_matches_phase15_formula(client, random_repo):
    user, ref = random_repo
    got = {i["number"]: i["hybrid"] for i in all_items(client, user)}
    for row in ref.itertuples():
        h = got[row.n]
        assert h["score"] == pytest.approx(row.want, abs=0.051)            # API rounds to 1 decimal
        assert h["size_percentile"] == pytest.approx(row.want_size, abs=0.051)
        assert h["llm_percentile"] == pytest.approx(row.want_llm, abs=0.051)


def test_sort_by_hybrid(client, random_repo):
    user, ref = random_repo
    order = [i["number"] for i in all_items(client, user)]
    want = list(ref.sort_values(["want", "n"], ascending=[False, False]).n)
    assert order[:len(ref)] == want           # same order as the research code, ties by PR number
    assert all(n not in set(ref.n) for n in order[len(ref):])   # unscored PRs last
    asc = client.get(f"{URL}?sort=hybrid&desc=false&limit=5", headers=auth(user)).json()["items"]
    assert [i["number"] for i in asc] == list(ref.sort_values(["want", "n"], ascending=[True, False]).n)[:5]


def test_detail_gives_the_same_hybrid_as_the_list(client, random_repo):
    user, ref = random_repo
    listed = {i["number"]: i["hybrid"] for i in all_items(client, user)}
    n = int(ref.n.iloc[0])
    assert client.get(f"{URL}/{n}", headers=auth(user)).json()["hybrid"] == listed[n]
    outside = next(i for i in listed if listed[i] is None)
    assert client.get(f"{URL}/{outside}", headers=auth(user)).json()["hybrid"] is None


def test_reference_is_per_repo(client, world):
    items = client.get("/repos/encode/httpx/prs?sort=hybrid", headers=auth(world["a"])).json()["items"]
    scored = [i for i in items if i["hybrid"]]
    assert sorted(i["number"] for i in scored) == [1, 2, 6, 7]   # churn + research RAG answer
    assert all(i["hybrid"]["reference_prs"] == 4 for i in scored)


def test_known_small_example(client, world):
    """Hand-checkable: churn 5, 50, 7, 50 and LLM 10, 70, 55, 70 for PRs 1, 2, 6, 7."""
    got = {i["number"]: i["hybrid"] for i in
           client.get("/repos/encode/httpx/prs?sort=hybrid", headers=auth(world["a"])).json()["items"] if i["hybrid"]}
    # churn ranks: 5->1, 7->2, 50,50->3.5 each; LLM ranks: 10->1, 55->2, 70,70->3.5 each; divide by 4
    assert got[1] == {"score": 25.0, "size_percentile": 25.0, "llm_percentile": 25.0, "reference_prs": 4}
    assert got[6] == {"score": 50.0, "size_percentile": 50.0, "llm_percentile": 50.0, "reference_prs": 4}
    assert got[2]["score"] == got[7]["score"] == 87.5
    assert np.isclose(got[2]["size_percentile"], 87.5)
