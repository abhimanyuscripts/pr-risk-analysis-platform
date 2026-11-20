"""Phase 15: does combining the size signal with the LLM+RAG signal beat either alone?

The design (which combination is the headline, which are exploratory, what counts
as an improvement) was written into docs/PROJECT_BIBLE.md before this was run.
Reads stored LLM answers only; never calls the LLM. Nothing is tuned on test labels.

Run from this folder:  python hybrid.py
"""
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine

from evaluate import evaluate
from hybrid_rules import higher_of, rank_average, tie_break
from load_dataset import FEATURES, load_training_table
from logreg import make_model
from rag_eval import MODEL, QUERY
from split import chronological_split

N_BOOT = 1000
CHURN, LOGREG, LLM = "churn rule (size)", "LogReg all 7", "LLM + docs (RAG)"
P, S1, S2, S3 = ("P  rank-average(churn, LLM)", "S1 churn, LLM breaks ties",
                 "S2 higher of the two", "S3 rank-average(LogReg, LLM)")


def paired_diff(y, a, b, n_boot=N_BOOT, seed=42):
    """AUC(a) - AUC(b) on the same bootstrap resamples. Returns (mean, low, high)."""
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        diffs.append(roc_auc_score(y[idx], a[idx]) - roc_auc_score(y[idx], b[idx]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(np.mean(diffs)), float(lo), float(hi)


def fmt(d):
    return f"{d[0]:+.3f} (95% {d[1]:+.3f} to {d[2]:+.3f})"


def analyze(train, test, llm):
    """Everything after loading: build the signals, combine, compare, print."""
    rag = llm[llm.use_rag][["github_pr_number", "risk_score"]].rename(columns={"risk_score": "llm_score"})
    t = test.merge(rag, on="github_pr_number").dropna(subset=["llm_score"]).reset_index(drop=True)
    assert t.github_pr_number.is_unique, "duplicate RAG answers for a PR"
    print(f"Label v3 | {MODEL}, prompt v1 | test PRs with a RAG answer: {len(t)} of {len(test)} "
          f"(risky {t.is_risky.mean():.1%})")
    if len(t) < len(test):
        print("  WARNING: some test PRs have no RAG answer; results cover only the answered ones.")
    if t.is_risky.nunique() < 2:
        raise SystemExit("Need risky and safe PRs among the answered ones.")

    y = t["is_risky"].astype(int).to_numpy()
    churn = t["churn"].to_numpy(dtype=float)
    llm_s = t["llm_score"].to_numpy(dtype=float)
    lr = make_model().fit(train[FEATURES].astype(float), train["is_risky"]) \
        .predict_proba(t[FEATURES].astype(float))[:, 1]       # trained on the training period only

    methods = {
        CHURN: churn, LOGREG: lr, LLM: llm_s,
        P: rank_average(churn, llm_s),
        S1: tie_break(churn, llm_s),
        S2: higher_of(churn, llm_s),
        S3: rank_average(lr, llm_s),
    }

    # Equal workload: every method flags (at least) as many PRs as the churn rule does.
    threshold = train["churn"].median()
    k = int((churn >= threshold).sum())
    flags = {}
    rows = []
    for name, score in methods.items():
        cutoff = np.sort(score)[::-1][k - 1]       # k-th highest score; ties at the cutoff are all flagged
        flags[name] = score >= cutoff
        e = evaluate(t["is_risky"], pd.Series(flags[name]), pd.Series(score))
        rows.append({"method": name, "roc_auc": e["roc_auc"], "flagged": int(flags[name].sum()),
                     "precision": e["precision"], "recall": e["recall"], "f1": e["f1"]})
    print(f"\nSAME TEST PRs (flagging about {k} PRs each, as many as 'churn >= {threshold:g}' does)")
    print(pd.DataFrame(rows).to_string(index=False))

    auc = {name: roc_auc_score(y, score) for name, score in methods.items()}
    d_churn = paired_diff(y, methods[P], churn)
    d_llm = paired_diff(y, methods[P], llm_s)
    print("\nPRE-DECLARED COMPARISONS FOR THE PRIMARY HYBRID P (paired AUC difference, "
          f"{N_BOOT:,} bootstrap resamples)")
    print("  P minus churn rule:", fmt(d_churn))
    print("  P minus LLM + RAG: ", fmt(d_llm))
    beats_both = auc[P] > auc[CHURN] and auc[P] > auc[LLM]
    excludes_zero = d_churn[1] > 0
    print(f"\nRULE FOR THE CLAIM: P beats both components: {'yes' if beats_both else 'no'} | "
          f"95% range of P - churn excludes 0: {'yes' if excludes_zero else 'no'}")
    if beats_both and excludes_zero:
        verdict = "P is a real improvement over both the size rule and the LLM+RAG score alone"
    elif excludes_zero:
        verdict = ("P clearly beats the size rule, but not the LLM+RAG score alone, "
                   "so the combination adds nothing over the best single signal")
    elif d_churn[2] < 0:
        verdict = "P is clearly WORSE than the size rule"
    else:
        verdict = "no clear difference from the size rule"
    print("  VERDICT:", verdict)

    print("\nEXPLORATORY (not part of the headline; several comparisons, so read with care)")
    for name in (S1, S2, S3):
        print(f"  {name} minus churn rule: {fmt(paired_diff(y, methods[name], churn))}")

    print("\nDIAGNOSTICS")
    print(f"  Spearman, churn vs LLM+RAG score:  {pd.Series(churn).corr(pd.Series(llm_s), method='spearman'):.2f}")
    print(f"  Spearman, LogReg vs LLM+RAG score: {pd.Series(lr).corr(pd.Series(llm_s), method='spearman'):.2f}")
    print(f"  distinct LLM+RAG scores: {pd.Series(llm_s).nunique()} (fewer values = more ties)")
    a, b, risky = flags[CHURN], flags[LLM], y == 1
    print(f"  Risky PRs caught (of {int(risky.sum())} risky). NOTE: churn flags {int(a.sum())} PRs but the LLM "
          f"flags {int(b.sum())} (tied scores), so this is not an equal-workload comparison: "
          f"churn only {int((a & ~b & risky).sum())}, "
          f"LLM only {int((~a & b & risky).sum())}, both {int((a & b & risky).sum())}, "
          f"neither {int((~a & ~b & risky).sum())}")


if __name__ == "__main__":
    df = load_training_table()
    train, test = chronological_split(df)
    with create_engine(os.getenv("DATABASE_URL")).connect() as conn:
        llm = pd.read_sql(QUERY, conn, params={"model": MODEL})
    analyze(train, test, llm)
