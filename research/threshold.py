"""Phase 10, Task 2: choose cut-offs on a validation slice instead of a blind 0.5.

Training PRs are split again by time: the oldest 80% fit the models, the newest
20% (closest in time to the test set) is used only to pick each cut-off. The
test set is never looked at until the final scoring.
"""
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

from evaluate import evaluate
from load_dataset import DEFAULT_LABEL_VERSION, FEATURES, load_training_table
from logreg import make_model
from split import chronological_split


def best_cutoff(y, score, candidates):
    """The candidate cut-off with the highest F1 on the validation slice."""
    f1s = [f1_score(y, score >= c, zero_division=0) for c in candidates]
    return candidates[int(np.argmax(f1s))]


if __name__ == "__main__":
    print(f"Label version: {os.getenv('LABEL_VERSION', DEFAULT_LABEL_VERSION)}")
    df = load_training_table()
    train, test = chronological_split(df)
    fit, val = chronological_split(train, 0.8)

    print("\nPARTS (all by merge date)")
    for name, part in [("fit", fit), ("validation", val), ("test", test)]:
        print(f"{name:11} {len(part):4} PRs  {part.merged_at.min().date()} to "
              f"{part.merged_at.max().date()}  risky {part.is_risky.mean():.1%}")

    X_fit, X_val, X_test = (p[FEATURES].astype(float) for p in (fit, val, test))
    logreg = make_model().fit(X_fit, fit["is_risky"])
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                random_state=42, n_jobs=-1).fit(X_fit, fit["is_risky"])

    # name: (validation score, test score, default cut-off, candidate cut-offs)
    churn_candidates = np.unique(np.percentile(val["churn"], range(1, 100)))
    prob_candidates = np.round(np.linspace(0.05, 0.95, 91), 2)
    methods = {
        "churn rule": (val["churn"].to_numpy(), test["churn"].to_numpy(),
                       fit["churn"].median(), churn_candidates),
        "LogReg all 7": (logreg.predict_proba(X_val)[:, 1], logreg.predict_proba(X_test)[:, 1],
                         0.5, prob_candidates),
        "Random Forest": (rf.predict_proba(X_val)[:, 1], rf.predict_proba(X_test)[:, 1],
                          0.5, prob_candidates),
    }

    rows = []
    for name, (val_score, test_score, default, candidates) in methods.items():
        tuned = best_cutoff(val["is_risky"], val_score, candidates)
        for label, cut in [("default", default), ("tuned on validation", tuned)]:
            pred = test_score >= cut
            rows.append({"method": name, "cut-off": f"{label} = {cut:g}",
                         "flagged": int(pred.sum()),
                         **evaluate(test["is_risky"], pred, test_score)})
    print("\nTEST SET RESULTS (models trained on the 'fit' part only)")
    print(pd.DataFrame(rows).to_string(index=False))
