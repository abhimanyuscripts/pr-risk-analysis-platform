"""Phase 9 follow-up: compare v2 and v3 labels on the same 1,294 PRs."""
import pandas as pd

from load_dataset import load_training_table

v2 = load_training_table(version=2)
v3 = load_training_table(version=3)
df = v2.merge(v3[["github_pr_number", "is_risky"]], on="github_pr_number", suffixes=("_v2", "_v3"))

print(f"PRs in both: {len(df)} (v2 rows {len(v2)}, v3 rows {len(v3)})")
print(f"Risky: v2 {df.is_risky_v2.sum()} ({df.is_risky_v2.mean():.1%}), "
      f"v3 {df.is_risky_v3.sum()} ({df.is_risky_v3.mean():.1%})")

print("\nHOW LABELS MOVED (rows = v2, columns = v3)")
print(pd.crosstab(df.is_risky_v2, df.is_risky_v3, margins=True))

print("\nRISKY RATE BY YEAR (%)")
by_year = df.groupby("year")[["is_risky_v2", "is_risky_v3"]].mean().mul(100).round(1)
by_year.insert(0, "prs", df.groupby("year").size())
print(by_year)

df["files"] = pd.cut(df.files_changed, [0, 1, 2, 4, 8, 10000], labels=["1", "2", "3-4", "5-8", "9+"])
df["has_tests"] = df.test_files_changed > 0
print("\nSIZE EFFECT: risky rate by files changed")
print(df.groupby("files", observed=True)[["is_risky_v2", "is_risky_v3"]].mean().round(2))

print("\nTEST-FILE EFFECT under v3 (same size band, without vs with test files)")
print(df.pivot_table(index="files", columns="has_tests", values="is_risky_v3",
                     aggfunc="mean", observed=True).round(2))
