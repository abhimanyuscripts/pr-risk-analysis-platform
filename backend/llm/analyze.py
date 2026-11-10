"""Phase 11: ask the LLM about one PR, check the answer, save it.

Every LLM call in the project goes through analyze_pr(), so switching provider
later means changing this file and client.py only.
"""
import time
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from database.models import ChangedFile, LLMAnalysis, PullRequest, Repository
from llm.client import GEMINI_MODEL, get_client
from llm.prompt import PROMPT_VERSION, build_prompt


class Concern(BaseModel):
    category: Literal["correctness", "security", "testing", "compatibility",
                      "performance", "maintainability"]
    file: str
    explanation: str


class RiskAnalysis(BaseModel):
    """The exact JSON shape the LLM must return; anything else is rejected."""
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high"]
    summary: str
    concerns: list[Concern]
    tests_included: bool


class LLMResponseError(Exception):
    """The model returned invalid JSON twice in a row."""


def analyze_pr(db: Session, pr: PullRequest, client=None, model: str = GEMINI_MODEL,
               use_rag: bool = False) -> tuple[LLMAnalysis, bool]:
    """Return (stored analysis, came_from_cache). Never asks twice for the same thing."""
    existing = db.query(LLMAnalysis).filter_by(
        pull_request_id=pr.id, model=model, prompt_version=PROMPT_VERSION, use_rag=use_rag
    ).first()
    if existing:
        return existing, True

    repo = db.get(Repository, pr.repository_id)
    files = db.query(ChangedFile).filter(ChangedFile.pull_request_id == pr.id).all()
    doc_chunks, retrieved = None, None
    if use_rag:
        from rag.retrieve import context_for_pr  # imported only for RAG (loads the embedding model)
        hits = context_for_pr(db, pr, files)
        doc_chunks = [(chunk.heading, chunk.content) for chunk, _ in hits]
        retrieved = [{"chunk_id": str(chunk.id), "heading": chunk.heading, "distance": round(dist, 4)}
                     for chunk, dist in hits]
    prompt, truncated = build_prompt(pr, files, repo.full_name, doc_chunks)

    client = client or get_client()
    config = types.GenerateContentConfig(
        temperature=0,                         # most repeatable answers
        response_mime_type="application/json",
        response_schema=RiskAnalysis,          # ask Gemini for exactly this shape
    )
    last_error = None
    for _ in range(2):                         # one retry if the JSON is broken
        start = time.time()
        response = client.models.generate_content(model=model, contents=prompt, config=config)
        latency_ms = int((time.time() - start) * 1000)
        try:
            result = RiskAnalysis.model_validate_json(response.text or "")
            break
        except ValidationError as exc:         # we still check it ourselves
            last_error = exc
    else:
        raise LLMResponseError(f"PR #{pr.github_pr_number}: invalid JSON twice: {last_error}")

    usage = response.usage_metadata
    row = LLMAnalysis(
        pull_request_id=pr.id, model=model, prompt_version=PROMPT_VERSION, use_rag=use_rag,
        risk_score=result.risk_score, risk_level=result.risk_level, result=result.model_dump(),
        diff_truncated=truncated, input_tokens=usage.prompt_token_count,
        output_tokens=usage.candidates_token_count, latency_ms=latency_ms,
        retrieved_chunks=retrieved,
    )
    db.add(row)
    db.commit()
    return row, False
