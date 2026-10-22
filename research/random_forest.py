"""Phase 9, Task 5: Random Forest vs Logistic Regression vs the churn rule."""
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance

from baseline_rule import score_baselines
from evaluate import evaluate
from load_dataset import FEATURES, load_training_table
from logreg import fit_and_score
from split import chronological_split, yearly_splits


def fit_rf(train, test):
    model = RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                   random_state=42, n_jobs=-1)
    model.fit(train[FEATURES].astype(float), train["is_risky"])
    prob = model.predict_proba(test[FEATURES].astype(float))[:, 1]
    pred = pd.Series(prob >= 0.5, index=test.index)
    return model, evaluate(test["is_risky"], pred, prob)


if __name__ == "__main__":
    df = load_training_table()
    train, test = chronological_split(df)

    rf, rf_scores = fit_rf(train, test)
    rows = [score_baselines(train, test)[1],
            {"method": "LogReg all 7", **fit_and_score(train, test, FEATURES)[1]},
            {"method": "Random Forest", **rf_scores}]
    print("MAIN SPLIT: test = 389 PRs, May 2022 to Dec 2025")
    print(pd.DataFrame(rows).to_string(index=False))

    imp = permutation_importance(rf, test[FEATURES].astype(float), test["is_risky"],
                                 scoring="roc_auc", n_repeats=20, random_state=42)
    print("\nIMPORTANCE (how much test ROC-AUC drops when the feature is shuffled)")
    print(pd.Series(imp.importances_mean, index=FEATURES).round(3)
          .sort_values(ascending=False).to_string())

    print("\nYEAR-BY-YEAR ROC-AUC")
    rows = []
    for year, tr, te in yearly_splits(df):
        rows.append({"test_year": year,
                     "churn rule": score_baselines(tr, te)[1]["roc_auc"],
                     "LogReg all 7": fit_and_score(tr, te, FEATURES)[1]["roc_auc"],
                     "Random Forest": fit_rf(tr, te)[1]["roc_auc"]})
    print(pd.DataFrame(rows).to_string(index=False))