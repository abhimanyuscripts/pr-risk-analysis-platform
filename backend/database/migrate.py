"""Bring an existing database up to date with the code: `python -m database.migrate` (run in backend/).

schema.sql creates a database from scratch. A database created earlier (your laptop, the Docker copy,
Neon) only needs the changes made since, listed here. Every statement is safe to run again, so the
Docker image runs this on each start.
"""
from sqlalchemy import text

from database.connection import engine

MIGRATIONS = [
    ("Phase 19: pr_labels.evidence (which later PR made a label risky)",
     "ALTER TABLE IF EXISTS pr_labels ADD COLUMN IF NOT EXISTS evidence JSONB"),
]


def main() -> None:
    with engine.begin() as conn:
        for name, statement in MIGRATIONS:
            conn.execute(text(statement))
            print(f"ok: {name}")


if __name__ == "__main__":
    main()
