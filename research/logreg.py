"""Phase 9, Task 4: Logistic Regression, size-only vs all features."""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from baseline_rule import score_baselines
from evaluate import evaluate
from load_dataset import FEATURES, load_training_table
from split import chronological_split, yearly_splits

FEATURE_SETS = {"LogReg size only": ["files_changed"], "LogReg all 7": FEATURES}


def make_model():
    # log1p tames huge PRs; the scaler and the model learn from training data only
    return make_pipeline(FunctionTransformer(np.log1p), StandardScaler(),
                         LogisticRegression(max_iter=1000))


def fit_and_score(train, test, cols):
    model = make_model()
    model.fit(train[cols].astype(float), train["is_risky"])
    prob = model.predict_proba(test[cols].astype(float))[:, 1]   # chance of "risky"
    pred = pd.Series(prob >= 0.5, index=test.index)
    return model, evaluate(test["is_risky"], pred, prob)


if __name__ == "__main__":
    df = load_training_table()
    train, test = chronological_split(df)

    rows = [score_baselines(train, test)[1]]          # churn rule, for comparison
    models = {}
    for name, cols in FEATURE_SETS.items():
        models[name], scores = fit_and_score(train, test, cols)
        rows.append({"method": name, **scores})
    print("MAIN SPLIT: test = 389 PRs, May 2022 to Dec 2025")
    print(pd.DataFrame(rows).to_string(index=False))

    weights = models["LogReg all 7"].named_steps["logisticregression"].coef_[0]
    print("\nWEIGHTS (all 7, after scaling; + means pushes toward risky)")
    print(pd.Series(weights, index=FEATURES).round(3).sort_values(ascending=False).to_string())

    print("\nYEAR-BY-YEAR ROC-AUC")
    rows = []
    for year, tr, te in yearly_splits(df):
        row = {"test_year": year, "churn rule": score_baselines(tr, te)[1]["roc_auc"]}
        for name, cols in FEATURE_SETS.items():
            row[name] = fit_and_score(tr, te, cols)[1]["roc_auc"]
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))