"""Phase 9, Task 2: build the time-based splits and show what's in each."""
import pandas as pd

from load_dataset import load_training_table


def chronological_split(df: pd.DataFrame, train_frac: float = 0.7):
    """Oldest train_frac of PRs for training, the rest for testing."""
    df = df.sort_values("merged_at").reset_index(drop=True)
    cut = int(len(df) * train_frac)
    return df.iloc[:cut], df.iloc[cut:]


def yearly_splits(df: pd.DataFrame):
    """For each year Y after the first: train on all earlier years, test on Y."""
    years = sorted(df["year"].unique())
    for test_year in years[1:]:
        train = df[df["year"] < test_year]
        test = df[df["year"] == test_year]
        yield test_year, train, test


def describe(name: str, part: pd.DataFrame) -> dict:
    return {
        "split": name,
        "prs": len(part),
        "from": part["merged_at"].min().date(),
        "to": part["merged_at"].max().date(),
        "risky": int(part["is_risky"].sum()),
        "risky_%": round(part["is_risky"].mean() * 100, 1),
    }


if __name__ == "__main__":
    df = load_training_table()

    train, test = chronological_split(df)
    assert train["merged_at"].max() <= test["merged_at"].min(), "test data leaked into training"
    print("MAIN SPLIT (70/30 by time)")
    print(pd.DataFrame([describe("train", train), describe("test", test)]).to_string(index=False))

    print("\nYEAR-BY-YEAR CHECK (train on earlier years, test on one year)")
    rows = []
    for year, tr, te in yearly_splits(df):
        rows.append({
            "test_year": year,
            "train_prs": len(tr),
            "train_risky_%": round(tr["is_risky"].mean() * 100, 1),
            "test_prs": len(te),
            "test_risky_%": round(te["is_risky"].mean() * 100, 1),
        })
    print(pd.DataFrame(rows).to_string(index=False))