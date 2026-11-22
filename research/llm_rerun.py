"""Phase 20, LLM noise check, step 1: ask Gemini AGAIN about every PR it already scored with docs.

Same model, same prompt (v1), same retrieval, temperature 0 (backend/llm/analyze.py builds the
prompt and asks, exactly as in Phase 14). Each answer is appended to results/llm_noise_run2.jsonl,
NOT to the database: the website and every earlier result keep using run 1. Every line also records
whether this run saw the same docs and the same number of input tokens as run 1, the evidence that
only the LLM differed.

Run from research/ with the backend venv active (it calls Gemini, so it runs on the laptop):
    python llm_rerun.py --limit 5      # a few first
    python llm_rerun.py                # the rest
Safe to stop and run again: PRs already in the file are skipped. At the free-tier daily limit
(HTTP 429) it stops by itself; run it again the next day.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import load_dataset  # noqa: F401  (loads backend/.env before the backend modules read it)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from google.genai import errors  # noqa: E402

from database.connection import SessionLocal  # noqa: E402
from database.models import LLMAnalysis, PullRequest, Repository  # noqa: E402
from llm.analyze import LLMResponseError, ask_llm, prepare_prompt  # noqa: E402
from llm.client import GEMINI_MODEL, get_client  # noqa: E402
from llm.prompt import PROMPT_VERSION  # noqa: E402

OUT = Path(__file__).resolve().parent / "results" / "llm_noise_run2.jsonl"


def already_done(path: Path) -> set[int]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row["model"] != GEMINI_MODEL or row["prompt_version"] != PROMPT_VERSION:
                raise SystemExit(f"{path.name} holds answers from another model or prompt; move it away first.")
            done.add(row["pr"])
    return done


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="encode/httpx")
    parser.add_argument("--limit", type=int, default=1000, help="max NEW model calls this run")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between calls")
    args = parser.parse_args()

    db = SessionLocal()
    owner, name = args.repo.split("/")
    repo = db.query(Repository).filter(Repository.owner == owner, Repository.name == name).one()
    # run 1: every PR with a stored answer WITH docs for this model and prompt (the Phase 14/15 answers)
    run1 = (db.query(PullRequest, LLMAnalysis)
            .join(LLMAnalysis, LLMAnalysis.pull_request_id == PullRequest.id)
            .filter(PullRequest.repository_id == repo.id, LLMAnalysis.model == GEMINI_MODEL,
                    LLMAnalysis.prompt_version == PROMPT_VERSION, LLMAnalysis.use_rag.is_(True))
            .order_by(PullRequest.merged_at).all())
    OUT.parent.mkdir(exist_ok=True)
    done = already_done(OUT)
    todo = [(pr, first) for pr, first in run1 if pr.github_pr_number not in done]
    print(f"{GEMINI_MODEL}, prompt v{PROMPT_VERSION}, with docs: {len(run1)} PRs answered in run 1, "
          f"{len(done)} already asked again, {len(todo)} to go (up to {args.limit} now)\n")

    client = get_client()
    new = failed = 0
    with OUT.open("a") as out:
        for pr, first in todo:
            if new + failed >= args.limit:
                break
            try:
                prompt, truncated, retrieved = prepare_prompt(db, pr, use_rag=True)
                result, usage, latency_ms = ask_llm(client, GEMINI_MODEL, prompt, pr.github_pr_number)
            except errors.ClientError as exc:
                if exc.code == 429:
                    print("Free-tier limit reached. Stopping; answers so far are saved, run again later.")
                    break
                print(f"#{pr.github_pr_number}: failed {exc.code} {exc.message}")
                failed += 1
                continue
            except (errors.ServerError, LLMResponseError) as exc:
                print(f"#{pr.github_pr_number}: failed {exc}")
                failed += 1
                continue

            same_docs = [c["chunk_id"] for c in retrieved] == [c["chunk_id"] for c in (first.retrieved_chunks or [])]
            same_tokens = usage.prompt_token_count == first.input_tokens
            row = {
                "pr": pr.github_pr_number, "model": GEMINI_MODEL, "prompt_version": PROMPT_VERSION, "run": 2,
                "risk_score": result.risk_score, "risk_level": result.risk_level,
                "run1_risk_score": first.risk_score,
                "same_docs_as_run1": same_docs, "same_input_tokens_as_run1": same_tokens,
                "input_tokens": usage.prompt_token_count, "output_tokens": usage.candidates_token_count,
                "latency_ms": latency_ms, "diff_truncated": truncated,
                "retrieved_chunk_ids": [c["chunk_id"] for c in retrieved],
                "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "result": result.model_dump(),
            }
            out.write(json.dumps(row) + "\n")
            out.flush()  # a crash or Ctrl+C never loses an answer already paid for
            new += 1
            flags = ("" if same_docs else ", OTHER DOCS") + ("" if same_tokens else ", other prompt length")
            print(f"#{pr.github_pr_number:<5} run 1 {first.risk_score:>3} -> run 2 {result.risk_score:>3} "
                  f"({result.risk_score - first.risk_score:+d}){flags}")
            time.sleep(args.pause)

    db.close()
    total = len(done) + new
    print(f"\nThis run: {new} new, {failed} failed. Asked again so far: {total} of {len(run1)}.")
    if total == len(run1):
        print("All done. Next: python llm_noise.py")


if __name__ == "__main__":
    main()
