"""Phase 16b: the Phase 15 hybrid score, computed for each PR inside the database.

Phase 15 (research/hybrid_rules.py) turned two signals into percentile ranks and averaged them:
    pct_rank(x) = average rank of x among all PRs / number of PRs     (ties share the average rank)
    hybrid      = (pct_rank(churn) + pct_rank(LLM+RAG score)) / 2
A single PR's percentile only means something against a fixed group of other PRs. The group used
here, the "reference", is every PR of the same repo that has a churn value and a stored answer from
the research LLM setup (GEMINI_MODEL, current prompt version, RAG on). For encode/httpx that is the
analysed test-period PRs. Labels are never used, so nothing here is tuned on the answer key.

Consequence to keep in mind: when more PRs get an LLM answer, the reference grows and every PR's
percentiles can shift slightly. The response says how many PRs the reference holds.
"""
from sqlalchemy import func, select

from database.models import LLMAnalysis, PRMetrics, PullRequest


def hybrid_subquery(repository_id, llm_model: str, prompt_version: int):
    """One row per reference PR: pr_id, size_pct, llm_pct (both in (0, 1]) and n (reference size)."""
    ref = (
        select(PullRequest.id.label("pr_id"), PRMetrics.churn.label("churn"),
               LLMAnalysis.risk_score.label("llm_score"))
        .join(PRMetrics, PRMetrics.pull_request_id == PullRequest.id)
        .join(LLMAnalysis, LLMAnalysis.pull_request_id == PullRequest.id)
        .where(PullRequest.repository_id == repository_id, PRMetrics.churn.is_not(None),
               LLMAnalysis.model == llm_model, LLMAnalysis.prompt_version == prompt_version,
               LLMAnalysis.use_rag.is_(True))
        .subquery("ref")
    )
    n = func.count().over()

    def pct(col):
        # rank() gives the lowest rank in a tie group (1-based); adding (tie size - 1) / 2 turns it
        # into the average rank, exactly like pandas rank(method="average") in Phase 15.
        avg_rank = func.rank().over(order_by=col) + (func.count().over(partition_by=col) - 1) / 2.0
        return avg_rank / n

    return select(ref.c.pr_id, pct(ref.c.churn).label("size_pct"), pct(ref.c.llm_score).label("llm_pct"),
                  n.label("n")).subquery("hybrid")
