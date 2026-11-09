"""Phase 11: analyse merged PRs since a date, saving every answer.

Run from backend/, starting small:
    python -m llm.run_batch --since 2022-05-26 --limit 5
Re-running skips PRs that already have a stored answer, so it is safe to stop
and continue later (for example after hitting the free-tier daily limit).
"""
import argparse
import json
import time
from datetime import date, datetime, timezone

from google.genai import errors

from database.connection import SessionLocal
from database.models import PullRequest, Repository
from llm.analyze import LLMResponseError, analyze_pr
from llm.client import GEMINI_MODEL, get_client

parser = argparse.ArgumentParser()
parser.add_argument("--repo", default="encode/httpx")
parser.add_argument("--since", type=date.fromisoformat, required=True)
parser.add_argument("--limit", type=int, default=5, help="max NEW model calls this run")
parser.add_argument("--pause", type=float, default=4.0, help="seconds between calls")
args = parser.parse_args()

db = SessionLocal()
owner, name = args.repo.split("/")
repo = db.query(Repository).filter(Repository.owner == owner, Repository.name == name).one()
since = datetime.combine(args.since, datetime.min.time(), tzinfo=timezone.utc)
prs = (db.query(PullRequest)
       .filter(PullRequest.repository_id == repo.id, PullRequest.merged_at >= since)
       .order_by(PullRequest.merged_at).all())
print(f"{len(prs)} merged PRs since {args.since}; model {GEMINI_MODEL}; up to {args.limit} new calls\n")

client = get_client()
calls = new = cached = failed = 0
shown_example = False
for pr in prs:
    if calls >= args.limit:
        break
    try:
        row, from_cache = analyze_pr(db, pr, client)
    except errors.ClientError as exc:
        if exc.code == 429:
            print("Free-tier limit reached. Stopping; saved answers are kept, re-run later to continue.")
            break
        print(f"#{pr.github_pr_number}: failed {exc.code} {exc.message}")
        db.rollback(); failed += 1; calls += 1
        continue
    except (errors.ServerError, LLMResponseError) as exc:
        print(f"#{pr.github_pr_number}: failed {exc}")
        db.rollback(); failed += 1; calls += 1
        continue

    if from_cache:
        cached += 1
        continue
    calls += 1; new += 1
    print(f"#{pr.github_pr_number:<5} score {row.risk_score:>3} {row.risk_level:<6} "
          f"{row.input_tokens} in / {row.output_tokens} out, {row.latency_ms} ms"
          f"{', diff cut' if row.diff_truncated else ''}  {pr.title[:50]}")
    if not shown_example:
        print("   example answer:", json.dumps(row.result, indent=2).replace("\n", "\n   "))
        shown_example = True
    time.sleep(args.pause)

db.close()
print(f"\nDone: {new} new, {cached} already stored, {failed} failed.")
