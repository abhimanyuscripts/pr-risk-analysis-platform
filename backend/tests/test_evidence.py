"""Label evidence (Phase 19): the API names the later PR and commit that made a label risky.

Timeline of the small repo below (days after 1 Jan 2024), all touching httpx/_client.py unless noted:
    PR 9  day 0   "fix" commit, merged BEFORE PR 1      -> must never count (no looking back)
    PR 1  day 1   the PR being labelled (also changes tests/test_client.py and docs/a.md)
    PR 3  day 5   "fix typo", only docs/a.md           -> counts for v1 (every file), not v2/v3
    PR 4  day 8   fix commit, only tests/test_client.py -> counts for v1/v2, not v3 (tests ignored)
    PR 2  day 10  "Bump" then "Fix proxies" commits     -> the v3 evidence
    PR 6  day 20  'Revert "Add client"'                 -> the revert evidence
    PR 5  day 70  fix commit, outside the 60-day window -> never counts
"""
from datetime import timedelta

import pytest

from database.models import PRLabel, PullRequest
from routes.labels import compute_label_for_pr
from tests.conftest import auth, dt

DETAIL = "/api/repos/encode/httpx/prs/1"


def day(n: int):
    return dt(2024, 1, 1) + timedelta(days=n)


@pytest.fixture
def timeline(seed, db):
    alice = seed.user("alice", 1)
    repo = seed.repo(alice, "encode", "httpx", 101)
    p9 = seed.pr(repo, 9, day(0))
    seed.file(p9, "httpx/_client.py", 1, 1)
    seed.commit(p9, "9" * 40, "Fix earlier bug", day(0))
    p1 = seed.pr(repo, 1, day(1), title="Add client")
    for name in ("httpx/_client.py", "tests/test_client.py", "docs/a.md"):
        seed.file(p1, name, 10, 0)
    seed.commit(p1, "1" * 40, "Add client", day(1))
    # stored before PRs 3 and 4 although merged after them: evidence must follow merge order
    p2 = seed.pr(repo, 2, day(10), title="Proxies")
    seed.file(p2, "httpx/_client.py", 3, 1)
    seed.commit(p2, "b" * 40, "Bump version", day(9))
    seed.commit(p2, "a" * 40, "Fix proxies\n\nThe keyword was dropped in #1.", day(10))
    p3 = seed.pr(repo, 3, day(5), title="Docs")
    seed.file(p3, "docs/a.md", 1, 1)
    seed.commit(p3, "3" * 40, "fix typo", day(5))
    p4 = seed.pr(repo, 4, day(8), title="Test only")
    seed.file(p4, "tests/test_client.py", 2, 0)
    seed.commit(p4, "4" * 40, "Fix flaky test", day(8))
    p6 = seed.pr(repo, 6, day(20), title='Revert "Add client"')
    seed.file(p6, "httpx/_client.py", 0, 10)
    p5 = seed.pr(repo, 5, day(70), title="Late")
    seed.file(p5, "httpx/_client.py", 1, 1)
    seed.commit(p5, "5" * 40, "fix late", day(70))
    db.commit()
    return alice


def label_with_evidence(client, user, version):
    assert client.post(f"/api/labels/compute/encode/httpx?version={version}", headers=auth(user)).status_code == 200
    labels = client.get(DETAIL, headers=auth(user)).json()["labels"]
    return next(lab for lab in labels if lab["version"] == version)


def test_v3_names_the_first_later_fix_on_a_source_file(client, timeline):
    lab = label_with_evidence(client, timeline, 3)
    assert lab["is_risky"] is True
    fix = lab["evidence"]["fix"]
    assert (fix["number"], fix["title"], fix["files"]) == (2, "Proxies", ["httpx/_client.py"])
    assert fix["merged_at"].startswith("2024-01-11")
    # the corrective commit, not the PR's first commit, and only its first line
    assert (fix["commit_sha"], fix["commit_message"]) == ("a" * 40, "Fix proxies")


def test_revert_evidence(client, timeline):
    revert = label_with_evidence(client, timeline, 3)["evidence"]["revert"]
    assert (revert["number"], revert["title"]) == (6, 'Revert "Add client"')


@pytest.mark.parametrize("version, number, files", [
    (1, 3, ["docs/a.md"]),             # v1 counts every file: the docs typo fix is the first match
    (2, 4, ["tests/test_client.py"]),  # v2 ignores docs, still counts test files
    (3, 2, ["httpx/_client.py"]),      # v3 ignores test files too
])
def test_each_label_version_follows_its_own_file_rule(client, timeline, version, number, files):
    fix = label_with_evidence(client, timeline, version)["evidence"]["fix"]
    assert (fix["number"], fix["files"]) == (number, files)


def test_labels_that_are_not_risky_have_no_evidence(client, timeline, db):
    label_with_evidence(client, timeline, 3)
    late = client.get("/api/repos/encode/httpx/prs/5", headers=auth(timeline)).json()["labels"][0]
    assert (late["is_risky"], late["evidence"]) == (False, None)
    stored = db.query(PRLabel).filter(PRLabel.is_risky.is_(False)).all()
    assert stored and all(lab.evidence is None for lab in stored)


def test_recording_evidence_never_changes_a_label(timeline, db):
    prs = db.query(PullRequest).all()
    for version in (1, 2, 3):
        for pr in prs:
            plain = compute_label_for_pr(pr, prs, db, version=version)
            recorded = compute_label_for_pr(pr, prs, db, version=version, evidence={"revert": None, "fix": None})
            assert plain == recorded


def test_long_commit_messages_are_cut(client, timeline, db, seed):
    p7 = seed.pr(db.query(PullRequest).filter_by(github_pr_number=1).one().repository, 7, day(3), title="Long")
    seed.file(p7, "httpx/_client.py", 1, 1)
    seed.commit(p7, "7" * 40, "fix " + "x" * 400, day(3))
    db.commit()
    message = label_with_evidence(client, timeline, 3)["evidence"]["fix"]["commit_message"]
    assert len(message) == 200 and message.endswith("…")


def test_old_or_broken_evidence_is_shown_as_none(client, timeline, db):
    label_with_evidence(client, timeline, 3)
    db.query(PRLabel).update({"evidence": {"fix": {"number": "not a number"}}})
    db.commit()
    r = client.get(DETAIL, headers=auth(timeline))
    assert r.status_code == 200
    assert all(lab["evidence"] is None for lab in r.json()["labels"])
