"""Phase 9: load the training table (encode/httpx, v2 labels, complete windows)."""
from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

FEATURES = [
    "files_changed", "lines_added", "lines_deleted", "churn",
    "commit_count", "test_files_changed", "is_sensitive_file",
]

QUERY = text("""
    SELECT pr.github_pr_number, pr.merged_at,
           m.files_changed, m.lines_added, m.lines_deleted, m.churn,
           m.commit_count, m.test_files_changed, m.is_sensitive_file,
           l.is_risky
    FROM pull_requests pr
    JOIN repositories r ON r.id = pr.repository_id
    JOIN pr_metrics  m ON m.pull_request_id = pr.id
    JOIN pr_labels   l ON l.pull_request_id = pr.id
    WHERE r.full_name = :repo
      AND l.label_version = :version
      AND l.window_complete = true
      AND pr.merged_at IS NOT NULL
    ORDER BY pr.merged_at
""")


def load_training_table(repo: str = "encode/httpx", version: int = 2) -> pd.DataFrame:
    engine = create_engine(os.getenv("DATABASE_URL"))
    with engine.connect() as conn:
        df = pd.read_sql(QUERY, conn, params={"repo": repo, "version": version})
    df["year"] = df["merged_at"].dt.year
    return df


if __name__ == "__main__":
    df = load_training_table()
    print("Rows, columns:", df.shape)
    print("Merged from", df["merged_at"].min().date(), "to", df["merged_at"].max().date())
    print(f"Risky: {df['is_risky'].sum()} of {len(df)} ({df['is_risky'].mean():.0%})")
    print("\nMissing values per column:")
    print(df.isna().sum())
    by_year = df.groupby("year")["is_risky"].agg(prs="size", risky="sum", rate="mean")
    by_year["rate"] = (by_year["rate"] * 100).round(0)
    print("\nRisky rate by merge year (%):")
    print(by_year)