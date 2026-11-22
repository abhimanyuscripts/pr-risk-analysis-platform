"""Phase 20b: does the documentation (RAG) help inside the hybrid?

The design and the rule for the verdict were written into docs/PROJECT_BIBLE.md (Phase 20b)
before this was run. Builds Phase 15's hybrid twice, once from the LLM's answers without docs
and once with docs, on the same test PRs. Reads stored answers only; never calls the LLM.

Run from this folder:  python ablation.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine

from hybrid import fmt, paired_diff
from hybrid_rules import rank_average
from load_dataset import load_training_table
from rag_eval import MODEL, QUERY
from split import chronological_split

RUN2 = Path(__file__).resolve().parent / "results" / "llm_noise_run2.jsonl"


def load_table() -> pd.DataFrame:
    """The labelled test PRs with churn, both run-1 LLM scores and (if present) run 2's docs score."""
    _, test = chronological_split(load_training_table())
    with create_engine(os.getenv("DATABASE_URL")).connect() as conn:
        llm = pd.read_sql(QUERY, conn, params={"model": MODEL})
    plain = llm[~llm.use_rag][["github_pr_number", "risk_score"]].rename(columns={"risk_score": "plain"})
    docs = llm[llm.use_rag][["github_pr_number", "risk_score"]].rename(columns={"risk_score": "docs"})
    t = test.merge(plain, on="github_pr_number").merge(docs, on="github_pr_number")
    if RUN2.exists():
        rows = [json.loads(line) for line in RUN2.read_text().splitlines() if line.strip()]
        run2 = pd.DataFrame({"github_pr_number": [r["pr"] for r in rows], "docs2": [r["risk_score"] for r in rows]})
        t = t.merge(run2, on="github_pr_number", how="left")
    assert t.github_pr_number.is_unique, "duplicate answers for a PR"
    return t.reset_index(drop=True)


def report(t: pd.DataFrame) -> None:
    y = t["is_risky"].astype(int).to_numpy()
    churn = t["churn"].to_numpy(dtype=float)
    plain = t["plain"].to_numpy(dtype=float)
    docs = t["docs"].to_numpy(dtype=float)
    p_plain, p_docs = rank_average(churn, plain), rank_average(churn, docs)
    auc = lambda s: roc_auc_score(y, s)

    print(f"ABLATION | {MODEL}, prompt v1 | {len(t)} labelled test PRs with both LLM answers "
          f"(risky {y.mean():.1%})")
    print("\nROC-AUC (checks: LLM without docs 0.731, with docs 0.763 and P_docs 0.843 must match Phases 11, 14, 15)")
    print(f"  size rule (churn)                          {auc(churn):.3f}")
    print(f"  LLM without docs                           {auc(plain):.3f}")
    print(f"  LLM with docs                              {auc(docs):.3f}")
    print(f"  P_plain = rank-average(churn, LLM no docs) {auc(p_plain):.3f}")
    print(f"  P_docs  = rank-average(churn, LLM docs)    {auc(p_docs):.3f}")

    d_main = paired_diff(y, p_docs, p_plain)
    print("\nPRE-DECLARED COMPARISON (paired AUC difference, 1,000 bootstrap resamples, seed 42)")
    print("  P_docs minus P_plain:   ", fmt(d_main))
    print("  P_plain minus size rule:", fmt(paired_diff(y, p_plain, churn)))
    print("\nRULE: RAG adds value inside the hybrid only if the 95% range of P_docs minus P_plain stays above 0.")
    print("  VERDICT:", "RAG ADDS VALUE inside the hybrid" if d_main[1] > 0 else
          "NO CLEAR DIFFERENCE: the docs did not measurably improve the hybrid")

    if "docs2" in t and t["docs2"].notna().all():
        docs2 = t["docs2"].to_numpy(dtype=float)
        print("\nEXPLORATORY (not part of the verdict): with-docs answers from run 2 (Phase 20a)")
        print("  P_docs(run 2) minus P_plain:           ", fmt(paired_diff(y, rank_average(churn, docs2), p_plain)))
        print("  LLM with docs (run 2) minus LLM no docs:", fmt(paired_diff(y, docs2, plain)),
              "  (Phase 14, run 1: +0.032, 95% +0.002 to +0.065)")
    else:
        print("\nEXPLORATORY skipped: run 2 answers missing for some PRs.")

    sp = lambda a, b: pd.Series(a).corr(pd.Series(b), method="spearman")
    print("\nDIAGNOSTICS (Spearman)")
    print(f"  churn vs LLM no docs {sp(churn, plain):.2f} | churn vs LLM docs {sp(churn, docs):.2f} | "
          f"LLM no docs vs LLM docs {sp(plain, docs):.2f}")


if __name__ == "__main__":
    report(load_table())
