"""Phase 9, Task 1: load the training table and check it matches Phase 8."""
from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Reuse the backend's database settings instead of copying the password here.
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
engine = create_engine(os.getenv("DATABASE_URL"))

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

with engine.connect() as conn:
    df = pd.read_sql(QUERY, conn, params={"repo": "encode/httpx", "version": 2})

print("Rows, columns:", df.shape)
print("Merged from", df["merged_at"].min().date(), "to", df["merged_at"].max().date())
print(f"Risky: {df['is_risky'].sum()} of {len(df)} ({df['is_risky'].mean():.0%})")
print("\nMissing values per column:")
print(df.isna().sum())

df["year"] = df["merged_at"].dt.year
by_year = df.groupby("year")["is_risky"].agg(prs="size", risky="sum", rate="mean")
by_year["rate"] = (by_year["rate"] * 100).round(0)
print("\nRisky rate by merge year (%):")
print(by_year)