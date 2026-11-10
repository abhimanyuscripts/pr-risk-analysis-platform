"""Phase 14: does giving the LLM the repository's docs (RAG) change its results?

Compares, on the same v3 test PRs: LLM without docs, LLM with docs, and the churn
rule. Reads stored answers only; never calls the LLM.
"""
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine, text

from evaluate import evaluate
from load_dataset import load_training_table
from split import chronological_split

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
QUERY = text("""
    SELECT pr.github_pr_number, a.use_rag, a.risk_score, a.risk_level, a.result,
           a.input_tokens, a.latency_ms, a.retrieved_chunks
    FROM llm_analyses a
    JOIN pull_requests pr ON pr.id = a.pull_request_id
    JOIN repositories r ON r.id = pr.repository_id
    WHERE r.full_name = 'encode/httpx' AND a.model = :model AND a.prompt_version = 1
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
    df = load_training_table()
    train, test = chronological_split(df)
    with create_engine(os.getenv("DATABASE_URL")).connect() as conn:
        llm = pd.read_sql(QUERY, conn, params={"model": MODEL})

    plain = llm[~llm.use_rag].add_suffix("_plain").rename(columns={"github_pr_number_plain": "github_pr_number"})
    rag = llm[llm.use_rag].add_suffix("_rag").rename(columns={"github_pr_number_rag": "github_pr_number"})
    t = test.merge(plain, on="github_pr_number").merge(rag, on="github_pr_number")
    print(f"Label v3 | {MODEL}, prompt v1 | test PRs with BOTH answers: {len(t)} of {len(test)} "
          f"(risky {t.is_risky.mean():.1%})")
    if t.is_risky.nunique() < 2:
        raise SystemExit("Need risky and safe PRs among the answered ones; run more RAG answers first.")

    y = t["is_risky"]
    threshold = train["churn"].median()
    churn = t["churn"].to_numpy()
    rows = [
        {"method": f"churn rule (>= {threshold:g})", **evaluate(y, churn >= threshold, churn)},
        {"method": "LLM, no docs", **evaluate(y, t.risk_level_plain != "low", t.risk_score_plain.to_numpy())},
        {"method": "LLM + docs (RAG)", **evaluate(y, t.risk_level_rag != "low", t.risk_score_rag.to_numpy())},
    ]
    print("\nSAME TEST PRs")
    print(pd.DataFrame(rows).to_string(index=False))

    yv = y.astype(int).to_numpy()
    print("\nPAIRED AUC DIFFERENCE (1,000 bootstrap resamples)")
    print("  RAG minus no-docs:", paired_auc_diff(yv, t.risk_score_rag.to_numpy(), t.risk_score_plain.to_numpy()))
    print("  RAG minus churn rule:", paired_auc_diff(yv, t.risk_score_rag.to_numpy(), churn))

    print("\nHOW THE ANSWERS CHANGED")
    print("  risk levels, no docs:", t.risk_level_plain.value_counts().to_dict())
    print("  risk levels, RAG:    ", t.risk_level_rag.value_counts().to_dict())
    print(f"  distinct scores: no docs {t.risk_score_plain.nunique()}, RAG {t.risk_score_rag.nunique()}")
    print(f"  same score in both: {(t.risk_score_plain == t.risk_score_rag).mean():.0%} of PRs; "
          f"rank correlation {t.risk_score_plain.corr(t.risk_score_rag, method='spearman'):.2f}")
    mentions = t.result_rag.map(lambda r: str(r).lower()).str.contains(r"\bdocs?\b|documentation|readme|contributing")
    print(f"  RAG answers that mention the docs (rough text check): {mentions.mean():.0%}")
    dist = t.retrieved_chunks_rag.map(lambda c: np.mean([x["distance"] for x in c]) if c else np.nan)
    print(f"  average retrieval distance: {dist.mean():.3f}  (lower = closer match)")
    print(f"  avg input tokens: no docs {t.input_tokens_plain.mean():.0f}, RAG {t.input_tokens_rag.mean():.0f} | "
          f"avg latency: no docs {t.latency_ms_plain.mean() / 1000:.1f} s, RAG {t.latency_ms_rag.mean() / 1000:.1f} s")
