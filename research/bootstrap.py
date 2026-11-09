"""Phase 10, Task 1: bootstrap confidence intervals on the 70/30 test set.

Resample the 389 test PRs with replacement many times, re-score every method on
each resample, and see how much the scores move. Methods are compared on the SAME
resample each time (paired), so the comparison only reflects the methods.
"""
import os

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score

from load_dataset import DEFAULT_LABEL_VERSION, FEATURES, load_training_table
from logreg import fit_and_score
from random_forest import fit_rf
from split import chronological_split

N_BOOT = 1000


def ci(values):
    lo, hi = np.percentile(values, [2.5, 97.5])
    return f"{lo:.3f} to {hi:.3f}"


if __name__ == "__main__":
    print(f"Label version: {os.getenv('LABEL_VERSION', DEFAULT_LABEL_VERSION)}")
    df = load_training_table()
    train, test = chronological_split(df)
    X_test = test[FEATURES].astype(float)
    y = test["is_risky"].astype(int).to_numpy()

    # Train each method once, on the training set only.
    threshold = train["churn"].median()
    logreg, _ = fit_and_score(train, test, FEATURES)
    rf, _ = fit_rf(train, test)
    lr_prob = logreg.predict_proba(X_test)[:, 1]
    rf_prob = rf.predict_proba(X_test)[:, 1]
    methods = {  # name: (score used for AUC, yes/no prediction used for F1)
        "churn rule": (test["churn"].to_numpy(), (test["churn"] >= threshold).to_numpy()),
        "LogReg all 7": (lr_prob, lr_prob >= 0.5),
        "Random Forest": (rf_prob, rf_prob >= 0.5),
    }

    rng = np.random.default_rng(42)
    auc = {m: [] for m in methods}
    f1 = {m: [] for m in methods}
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(y), len(y))      # pick 389 PRs, repeats allowed
        yb = y[idx]
        if yb.min() == yb.max():                   # need risky AND safe PRs to score
            continue
        for m, (score, pred) in methods.items():
            auc[m].append(roc_auc_score(yb, score[idx]))
            f1[m].append(f1_score(yb, pred[idx]))

    print(f"\nEACH METHOD on the test set (95% range over {N_BOOT} resamples)")
    rows = []
    for m, (score, pred) in methods.items():
        rows.append({"method": m,
                     "roc_auc": round(roc_auc_score(y, score), 3), "auc_95%": ci(auc[m]),
                     "f1": round(f1_score(y, pred), 3), "f1_95%": ci(f1[m])})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nIS A MODEL REALLY BETTER THAN THE CHURN RULE? (paired AUC difference)")
    rows = []
    for m in ["LogReg all 7", "Random Forest"]:
        d = np.array(auc[m]) - np.array(auc["churn rule"])
        lo, hi = np.percentile(d, [2.5, 97.5])
        rows.append({"comparison": f"{m} minus rule",
                     "avg_diff": round(d.mean(), 3), "diff_95%": ci(d),
                     "model_ahead_in": f"{(d > 0).mean():.0%} of resamples",
                     "verdict": "real difference" if lo > 0 or hi < 0 else "no clear difference"})
    print(pd.DataFrame(rows).to_string(index=False))
