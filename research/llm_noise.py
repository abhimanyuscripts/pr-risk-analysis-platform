"""Phase 20, LLM noise check, step 2: how much did the scores change, and does the hybrid's gain survive?

The questions, numbers and the rule for the verdict were written into docs/PROJECT_BIBLE.md
(Phase 20) BEFORE run 2 was collected. Reads run 1 from the database and run 2 from
results/llm_noise_run2.jsonl (made by llm_rerun.py); never calls the LLM.

Run from this folder:  python llm_noise.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, roc_auc_score
from sqlalchemy import create_engine

from hybrid import fmt, paired_diff
from hybrid_rules import rank_average
from load_dataset import load_training_table
from rag_eval import MODEL, QUERY
from split import chronological_split

RUN2 = Path(__file__).resolve().parent / "results" / "llm_noise_run2.jsonl"


def load_runs():
    with create_engine(os.getenv("DATABASE_URL")).connect() as conn:
        llm = pd.read_sql(QUERY, conn, params={"model": MODEL})
    run1 = (llm[llm.use_rag][["github_pr_number", "risk_score", "risk_level"]]
            .rename(columns={"risk_score": "score1", "risk_level": "level1"}))
    rows = [json.loads(line) for line in RUN2.read_text().splitlines() if line.strip()]
    run2 = pd.DataFrame([{"github_pr_number": r["pr"], "score2": r["risk_score"], "level2": r["risk_level"],
                          "same_prompt": r["same_docs_as_run1"] and r["same_input_tokens_as_run1"],
                          "same_docs": r["same_docs_as_run1"], "model": r["model"]} for r in rows])
    assert run2.github_pr_number.is_unique, "a PR appears twice in run 2"
    assert (run2.model == MODEL).all(), "run 2 holds answers from another model"
    return run1, run2


def agreement(pairs: pd.DataFrame, title: str) -> None:
    d = (pairs.score2 - pairs.score1).abs()
    print(f"\n{title} ({len(pairs)} PRs)")
    if pairs.empty:
        return
    print(f"  same score:          {(d == 0).mean():.1%}")
    print(f"  score change |run 2 - run 1|: mean {d.mean():.1f}, median {d.median():.0f}, "
          f"90th percentile {d.quantile(0.9):.0f}, largest {d.max():.0f}  (scores are 0-100)")
    print(f"  Spearman correlation of the two runs: {pairs.score1.corr(pairs.score2, method='spearman'):.3f}")
    print(f"  same risk level (low/medium/high): {(pairs.level1 == pairs.level2).mean():.1%}, "
          f"Cohen's kappa {cohen_kappa_score(pairs.level1, pairs.level2):.2f}")


def p_minus_churn(t: pd.DataFrame, llm_scores: np.ndarray):
    y = t["is_risky"].astype(int).to_numpy()
    churn = t["churn"].to_numpy(dtype=float)
    p = rank_average(churn, llm_scores)
    return roc_auc_score(y, p), paired_diff(y, p, churn)


def main() -> None:
    if not RUN2.exists():
        raise SystemExit(f"{RUN2.name} not found: run llm_rerun.py first.")
    run1, run2 = load_runs()
    pairs = run1.merge(run2, on="github_pr_number")
    print(f"{MODEL}, prompt v1, with docs | run 1: {len(run1)} PRs, run 2 so far: {len(run2)}")
    print(f"  run 2 saw the same docs as run 1 for {pairs.same_docs.mean():.1%} of PRs, "
          f"and the same prompt (same docs and same input token count) for {pairs.same_prompt.mean():.1%}")

    agreement(pairs, "AGREEMENT, ALL PRs ASKED TWICE")
    agreement(pairs[pairs.same_prompt], "AGREEMENT, ONLY PRs WHOSE PROMPT WAS PROVABLY THE SAME (pure LLM noise)")
    agreement(pairs[~pairs.same_prompt], "AGREEMENT, PRs WHOSE PROMPT DIFFERED (docs or length)")

    train, test = chronological_split(load_training_table())
    t = test.merge(pairs, on="github_pr_number").reset_index(drop=True)
    covered = test.github_pr_number.isin(run1.github_pr_number).sum()
    if len(t) < covered:
        print(f"\nHEADLINE WAITS: run 2 covers {len(t)} of the {covered} labelled test PRs that run 1 covers. "
              "Finish llm_rerun.py first; the pre-declared verdict needs all of them.")
        return

    y = t["is_risky"].astype(int).to_numpy()
    s1, s2 = t["score1"].to_numpy(dtype=float), t["score2"].to_numpy(dtype=float)
    print(f"\nSAME {len(t)} LABELLED TEST PRs (label v3, risky {y.mean():.1%})")
    print(f"  LLM + docs ROC-AUC: run 1 {roc_auc_score(y, s1):.3f}, run 2 {roc_auc_score(y, s2):.3f}, "
          f"run 2 minus run 1 {fmt(paired_diff(y, s2, s1))}")
    churn_auc = roc_auc_score(y, t['churn'].to_numpy(dtype=float))
    auc1, d1 = p_minus_churn(t, s1)
    auc2, d2 = p_minus_churn(t, s2)
    print(f"  size rule ROC-AUC: {churn_auc:.3f} (does not use the LLM)")
    print(f"  hybrid P ROC-AUC:  run 1 {auc1:.3f}, run 2 {auc2:.3f}")
    print(f"  P minus size rule: run 1 {fmt(d1)}   <- must equal Phase 15 (+0.039, 95% +0.002 to +0.076)")
    print(f"                     run 2 {fmt(d2)}")

    robust = d2[1] > 0
    print("\nPRE-DECLARED RULE: the Phase 15 gain counts as robust to LLM noise if, with run 2's scores,")
    print("the 95% range of 'P minus size rule' stays above 0.")
    print("  VERDICT:", "ROBUST: the gain over the size rule holds with a second LLM run" if robust else
          "NOT ROBUST: with a second LLM run the gain over the size rule is no longer clear")

    _, d_avg = p_minus_churn(t, (s1 + s2) / 2)
    print("\nEXPLORATORY (not part of the verdict): LLM score = average of the two runs")
    print(f"  P minus size rule: {fmt(d_avg)}")


if __name__ == "__main__":
    main()
