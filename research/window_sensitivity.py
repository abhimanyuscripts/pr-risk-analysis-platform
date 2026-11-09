"""Phase 10, Task 3: does the conclusion depend on the 60-day label window?

Relabels encode/httpx with the v3 rule at 30, 60 and 90 days IN MEMORY (nothing
is written to pr_labels), reusing the exact labeling code from the backend, then
re-runs the 70/30 comparison for each window. The 60-day run must reproduce the
stored v3 figures (1,294 PRs, 520 risky); that is the pipeline check.
"""
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import text

from load_dataset import FEATURES  # loads backend/.env first

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from database.connection import SessionLocal, engine  # noqa: E402
from database.models import PullRequest, Repository  # noqa: E402
from routes.labels import compute_label_for_pr  # noqa: E402

from baseline_rule import score_baselines  # noqa: E402
from logreg import fit_and_score  # noqa: E402
from random_forest import fit_rf  # noqa: E402
from split import chronological_split  # noqa: E402

REPO = "encode/httpx"
WINDOWS = [30, 60, 90]
METRICS_QUERY = text("""
    SELECT pr.id, pr.github_pr_number, pr.merged_at,
           m.files_changed, m.lines_added, m.lines_deleted, m.churn,
           m.commit_count, m.test_files_changed, m.is_sensitive_file
    FROM pull_requests pr
    JOIN repositories r ON r.id = pr.repository_id
    JOIN pr_metrics  m ON m.pull_request_id = pr.id
    WHERE r.full_name = :repo AND pr.merged_at IS NOT NULL
""")


def label_all(window_days: int) -> pd.DataFrame:
    db = SessionLocal()
    try:
        owner, name = REPO.split("/")
        repo = db.query(Repository).filter(Repository.owner == owner, Repository.name == name).one()
        all_prs = db.query(PullRequest).filter(PullRequest.repository_id == repo.id).all()
        data_end = max(p.merged_at for p in all_prs if p.merged_at is not None)
        rows = []
        for pr in all_prs:
            if pr.state != "merged" or pr.merged_at is None:
                continue
            risky, _ = compute_label_for_pr(pr, all_prs, db, version=3, window_days=window_days)
            rows.append({"id": str(pr.id), "is_risky": risky,
                         "window_complete": pr.merged_at + timedelta(days=window_days) <= data_end})
        return pd.DataFrame(rows)
    finally:
        db.close()


def paired_auc_diff(y, a, b, n_boot=1000, seed=42):
    """95% range of AUC(a) - AUC(b) over paired bootstrap resamples of the test set."""
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        diffs.append(roc_auc_score(y[idx], a[idx]) - roc_auc_score(y[idx], b[idx]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return f"{np.mean(diffs):+.3f} ({lo:+.3f} to {hi:+.3f})"


if __name__ == "__main__":
    with engine.connect() as conn:
        metrics = pd.read_sql(METRICS_QUERY, conn, params={"repo": REPO})
    metrics["id"] = metrics["id"].astype(str)

    rows = []
    for w in WINDOWS:
        print(f"Labeling with a {w}-day window (v3 rule)...", flush=True)
        df = metrics.merge(label_all(w), on="id")
        df = df[df["window_complete"]].sort_values("merged_at").reset_index(drop=True)
        df["year"] = df["merged_at"].dt.year
        train, test = chronological_split(df)

        rule = score_baselines(train, test)[1]
        lr_model, lr = fit_and_score(train, test, FEATURES)
        _, rf = fit_rf(train, test)
        y = test["is_risky"].astype(int).to_numpy()
        lr_prob = lr_model.predict_proba(test[FEATURES].astype(float))[:, 1]
        rows.append({
            "window": f"{w} days", "prs": len(df), "risky_%": round(df.is_risky.mean() * 100, 1),
            "train_risky_%": round(train.is_risky.mean() * 100, 1),
            "test_risky_%": round(test.is_risky.mean() * 100, 1),
            "rule_auc": rule["roc_auc"], "logreg_auc": lr["roc_auc"], "rf_auc": rf["roc_auc"],
            "rule_f1": rule["f1"], "logreg_f1": lr["f1"], "rf_f1": rf["f1"],
            "logreg_minus_rule_auc (95%)": paired_auc_diff(y, lr_prob, test["churn"].to_numpy()),
        })

    print("\nRESULTS BY LABEL WINDOW (v3 rule, chronological 70/30 split)")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nCheck: the 60-day row should show 1294 PRs and 40.2% risky (stored v3 labels).")
