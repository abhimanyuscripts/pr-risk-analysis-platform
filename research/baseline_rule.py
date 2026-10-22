"""Phase 9, Task 3: rule-based baseline (no learning) and a flag-everything floor."""
import pandas as pd

from evaluate import evaluate
from load_dataset import load_training_table
from split import chronological_split, yearly_splits


def score_baselines(train: pd.DataFrame, test: pd.DataFrame) -> list[dict]:
    y = test["is_risky"]
    threshold = train["churn"].median()          # learned from TRAINING data only
    rule_pred = test["churn"] >= threshold
    flag_all = pd.Series(True, index=test.index)
    return [
        {"method": "flag everything", **evaluate(y, flag_all, pd.Series(1.0, index=test.index))},
        {"method": f"churn >= {threshold:g}", **evaluate(y, rule_pred, test["churn"])},
    ]


if __name__ == "__main__":
    df = load_training_table()

    train, test = chronological_split(df)
    print("MAIN SPLIT: test = 389 PRs, May 2022 to Dec 2025")
    print(pd.DataFrame(score_baselines(train, test)).to_string(index=False))

    print("\nYEAR-BY-YEAR (churn rule only)")
    rows = []
    for year, tr, te in yearly_splits(df):
        rule = score_baselines(tr, te)[1]
        rows.append({"test_year": year, **rule})
    print(pd.DataFrame(rows).to_string(index=False))