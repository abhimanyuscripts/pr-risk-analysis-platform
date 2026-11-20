"""Phase 16b check: does the hybrid the API serves match Phase 15's result on the real data?

Reads the hybrid percentiles straight from the database query the API uses (backend/scoring.py),
joins them to the v3 test PRs and computes ROC-AUC. Phase 15 measured 0.843 for the same formula.
The API's reference group can hold a PR or two more than Phase 15's 389 test PRs (any analysed PR
counts), so a difference in the third decimal is expected; a large one means a bug.

Run from this folder:  python hybrid_db_check.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from scoring import hybrid_subquery  # noqa: E402  (same query as the API)
from database.models import PullRequest, Repository  # noqa: E402

from load_dataset import load_training_table  # noqa: E402
from split import chronological_split  # noqa: E402

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
PHASE15_AUC = 0.843

if __name__ == "__main__":
    train, test = chronological_split(load_training_table())
    engine = create_engine(os.getenv("DATABASE_URL"))
    with engine.connect() as conn:
        repo_id = conn.execute(select(Repository.id).where(Repository.full_name == "encode/httpx")).scalar_one()
        hyb = hybrid_subquery(repo_id, MODEL, 1)
        rows = conn.execute(
            select(PullRequest.github_pr_number, hyb.c.size_pct, hyb.c.llm_pct, hyb.c.n)
            .join(hyb, hyb.c.pr_id == PullRequest.id)
        ).all()
    h = pd.DataFrame(rows, columns=["github_pr_number", "size_pct", "llm_pct", "n"]).astype(
        {"size_pct": float, "llm_pct": float})
    t = test.merge(h, on="github_pr_number")
    print(f"Reference PRs in the API: {int(h.n.iloc[0])} | test PRs with a hybrid: {len(t)} of {len(test)}")
    auc = roc_auc_score(t.is_risky.astype(int), t.size_pct + t.llm_pct)
    print(f"ROC-AUC of the API hybrid on the test PRs: {auc:.3f}   (Phase 15: {PHASE15_AUC})")
    print("MATCH" if abs(auc - PHASE15_AUC) <= 0.005 else "MISMATCH: check before trusting the dashboard score")
