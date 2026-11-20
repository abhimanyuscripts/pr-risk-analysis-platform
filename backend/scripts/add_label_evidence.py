"""Phase 19: store WHICH later PR made each risky label risky, without changing any label.

Run from backend/ after `python -m database.migrate`:
    python scripts/add_label_evidence.py encode/httpx

For every stored label (all versions) it re-runs the labelling rule with evidence recording on. If the
recomputed risky/not-risky answer differs from the stored one for even one PR (the data changed since
labelling), it stops and writes nothing: relabel with POST /api/labels/compute first. Otherwise it only
fills pr_labels.evidence; is_risky, reasons and labeled_at stay exactly as they were.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal  # noqa: E402
from database.models import PRLabel, PullRequest, Repository  # noqa: E402
from routes.labels import compute_label_for_pr  # noqa: E402


def main(full_name: str) -> int:
    db = SessionLocal()
    try:
        repository = db.query(Repository).filter(Repository.full_name == full_name).first()
        if repository is None:
            print(f"No repository {full_name!r} in this database.")
            return 1
        prs = db.query(PullRequest).filter(PullRequest.repository_id == repository.id).all()
        by_id = {p.id: p for p in prs}
        labels = db.query(PRLabel).filter(PRLabel.pull_request_id.in_(list(by_id))).all()
        print(f"{full_name}: {len(prs)} PRs, {len(labels)} stored labels")

        started = time.time()
        updates, changed = [], []
        for i, label in enumerate(labels, start=1):
            pr = by_id[label.pull_request_id]
            evidence = {"revert": None, "fix": None}
            risky, _ = compute_label_for_pr(pr, prs, db, version=label.label_version,
                                            window_days=label.label_window_days, evidence=evidence)
            if risky != label.is_risky:
                changed.append((pr.github_pr_number, label.label_version, label.is_risky, risky))
            updates.append((label, evidence if risky else None))
            if i % 500 == 0:
                print(f"  {i}/{len(labels)} checked ({time.time() - started:.0f}s)")

        if changed:
            print(f"STOPPED: {len(changed)} labels would change, so the stored labels are out of date. Nothing written.")
            for number, version, old, new in changed[:20]:
                print(f"  PR #{number} v{version}: stored {old}, now {new}")
            return 2

        for label, evidence in updates:
            label.evidence = evidence
        db.commit()
        with_fix = sum(1 for _, e in updates if e and e["fix"])
        with_revert = sum(1 for _, e in updates if e and e["revert"])
        print(f"Done in {time.time() - started:.0f}s. 0 labels changed. Evidence stored for "
              f"{sum(1 for _, e in updates if e)} risky labels ({with_fix} with a fix PR, {with_revert} with a revert).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
