"""Phase 11, Task 4: score the stored LLM answers on the same test PRs as the ML models.

Reads llm_analyses (never calls the LLM), joins it to the v3 70/30 test set, and
compares the LLM with the churn rule and Logistic Regression on exactly the same PRs.
"""
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine, text

from evaluate import evaluate
from load_dataset import DEFAULT_LABEL_VERSION, FEATURES, load_training_table
from logreg import fit_and_score
from split import chronological_split

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
PROMPT_VERSION = int(os.getenv("PROMPT_VERSION", "1"))

LLM_QUERY = text("""
    SELECT pr.github_pr_number, a.risk_score, a.risk_level, a.diff_truncated,
           a.input_tokens, a.output_tokens, a.latency_ms
    FROM llm_analyses a
    JOIN pull_requests pr ON pr.id = a.pull_request_id
    JOIN repositories r ON r.id = pr.repository_id
    WHERE r.full_name = 'encode/httpx' AND a.model = :model
      AND a.prompt_version = :pv AND a.use_rag = false
""")


def paired_auc_diff(y, a, b, n_boot=1000, seed=42):
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        diffs.append(roc_auc_score(y[idx], a[idx]) - roc_auc_score(y[idx], b[idx]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    verdict = "real difference" if lo > 0 or hi < 0 else "no clear difference"
    return f"{np.mean(diffs):+.3f} (95% {lo:+.3f} to {hi:+.3f}) -> {verdict}"


if __name__ == "__main__":
    print(f"Label v{os.getenv('LABEL_VERSION', DEFAULT_LABEL_VERSION)} | LLM {MODEL}, prompt v{PROMPT_VERSION}, no RAG")
    df = load_training_table()
    train, test = chronological_split(df)
    with create_engine(os.getenv("DATABASE_URL")).connect() as conn:
        llm = pd.read_sql(LLM_QUERY, conn, params={"model": MODEL, "pv": PROMPT_VERSION})

    t = test.merge(llm, on="github_pr_number", how="inner")
    print(f"Test PRs with an LLM answer: {len(t)} of {len(test)}  (risky: {t.is_risky.mean():.1%})")
    if t.is_risky.nunique() < 2:
        raise SystemExit("Need both risky and safe PRs among the answered ones; analyse more PRs first.")

    threshold = train["churn"].median()
    logreg, _ = fit_and_score(train, test, FEATURES)
    y = t["is_risky"]
    rule_score = t["churn"].to_numpy()
    lr_prob = logreg.predict_proba(t[FEATURES].astype(float))[:, 1]
    llm_score = t["risk_score"].to_numpy()

    rows = [
        {"method": f"churn rule (>= {threshold:g})", **evaluate(y, rule_score >= threshold, rule_score)},
        {"method": "LogReg all 7", **evaluate(y, lr_prob >= 0.5, lr_prob)},
        {"method": "LLM (medium/high = risky)", **evaluate(y, t["risk_level"] != "low", llm_score)},
    ]
    print("\nSAME TEST PRs, ALL METHODS")
    print(pd.DataFrame(rows).to_string(index=False))

    yv = y.astype(int).to_numpy()
    print("\nPAIRED AUC DIFFERENCE (1,000 bootstrap resamples)")
    print("  LLM minus churn rule:", paired_auc_diff(yv, llm_score, rule_score))
    print("  LLM minus LogReg:    ", paired_auc_diff(yv, llm_score, lr_prob))

    print("\nWHAT THE LLM SCORE LOOKS LIKE")
    print("  risk levels:", t["risk_level"].value_counts().to_dict())
    print(f"  distinct scores: {t.risk_score.nunique()}  (many ties make ranking coarse)")
    print("  mean score, labeled risky vs safe:",
          t.groupby("is_risky")["risk_score"].mean().round(1).to_dict())
    print("  rank correlation (Spearman) of LLM score with churn:",
          round(t["risk_score"].corr(t["churn"], method="spearman"), 3),
          "| with files_changed:", round(t["risk_score"].corr(t["files_changed"], method="spearman"), 3))
    print(f"  diff cut short: {int(t.diff_truncated.sum())} PRs | avg tokens {t.input_tokens.mean():.0f} in / "
          f"{t.output_tokens.mean():.0f} out | avg latency {t.latency_ms.mean() / 1000:.1f} s")
