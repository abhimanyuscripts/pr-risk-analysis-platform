# PROJECT BIBLE
## AI-Powered Pull Request Risk Analysis & Software Engineering Intelligence Platform

*Living document — update after every phase. Last updated: Phase 1.*
---

## 1. Objective
Full-stack platform that gives an explainable PR risk assessment using traditional SE metrics, ML, RAG-grounded LLM semantic analysis, and a hybrid combiner — with a genuine, non-assumed research comparison of whether combining these actually helps.

## 2. Core Research Question
> Does combining traditional PR metrics, ML-based risk prediction, and RAG-enhanced LLM semantic analysis produce a more accurate and more informative PR risk assessment than using each approach individually?
(Revised from "more useful" — split into two measurable dimensions: predictive accuracy (F1/ROC-AUC, for the ML-comparable parts) and informativeness (rubric-scored relevance/specificity/actionability, for the LLM+RAG qualitative parts) so the claim is falsifiable, not just a vibe.)

## 3. Secondary Research Questions
1. Does RAG-retrieved repo context change LLM output relevance/specificity/hallucination rate vs. no context?
2. Which traditional metric group is most predictive?
3. Does the hybrid combination measurably beat ML-only or LLM(+RAG)-only?
4. What's the latency/cost overhead of RAG+LLM vs. the accuracy/informativeness gained?

## 4. Risk Label (simplified, no SZZ)
A PR has "subsequent corrective activity associated with it" (risky) if, within a fixed post-merge window W:
- it was explicitly reverted, **or**
- it's referenced by an issue labeled bug/regression, **or**
- a file it touched received a fix-pattern commit.
Deliberately non-causal wording — we never claim the PR *caused* the bug, only that corrective activity is *associated* with it. Documented limitations: coincidental file overlap, inconsistent commit conventions, delayed bug surfacing. SZZ line-tracing = future work.

## 5. RAG's Exact Role
Ground the LLM in *this specific repo's* conventions (coding/security/testing guidelines, docs) instead of generic advice — e.g. "no auth tests" becomes "repo guideline requires token-expiration + invalid-token tests, none detected." NOT for retrieving similar historical PRs or indexing the full codebase (future scope).

## 6. RAG Pipeline (simple)
```
Repo docs (README, CONTRIBUTING, docs/, guidelines)
  → chunk → embed → store in Postgres+pgvector
  → similarity search (top-K) → context builder → LLM
```

## 7. Experiment Design
1. Traditional rule-based heuristic (no learning) — sanity floor
2. ML on traditional metrics (LR/RF, XGBoost if justified)
3. LLM without RAG
4. LLM with RAG
5. Hybrid (ML + LLM/RAG)
6. Ablation: hybrid-without-RAG vs. hybrid-with-RAG (isolates RAG's marginal value), + label-window sensitivity
LLM-based experiments get a small (~20-30 PR) reproducible manual rubric eval (relevance/specificity/actionability/hallucination) in addition to F1/ROC-AUC via thresholding — never fabricated.

## 8. MVP — MUST / GOOD / FUTURE
**MUST HAVE:** auth, GitHub integration, repo/PR retrieval, metric extraction, dataset+labeling, LR+RF, LLM structured JSON analysis, basic RAG (docs + pgvector + top-K), hybrid engine (simple transparent combination first), explainable dashboard, Postgres, API validation/JWT/secrets hygiene, Docker+compose, basic GitHub Actions CI, one simple cloud deployment.
**GOOD TO HAVE:** XGBoost (if time/data justify), SHAP, calibrated meta-model combiner, small RAG-eval rubric study, label-window sensitivity check, cross-repo generalization check.
**FUTURE SCOPE:** SZZ, GraphQL (unless REST insufficient), Celery/Redis, microservices, Kubernetes, advanced reranking, autonomous/multi-agent, full codebase indexing, similar-PR retrieval, webhooks/auto-comments/status checks, multi-repo enterprise, drift detection, auto-retraining.

## 9. Architecture
```
User → Next.js → FastAPI → Auth → GitHub Integration
  → Analysis Pipeline
      ├── Metrics Engine
      ├── ML Engine
      ├── RAG Engine (loader → chunker → embeddings → pgvector search → context builder)
      ├── LLM Engine
      └── Hybrid Risk Engine
  → PostgreSQL + pgvector → Dashboard
```
Modular monolith. No Celery/Redis unless latency actually demands it.

## 10. Tech Stack (reasons)
Same as v1 (Next.js/React/TS/Tailwind, FastAPI/Pydantic/SQLAlchemy, PostgreSQL, scikit-learn/XGBoost/SHAP) **plus**:
- **pgvector over a dedicated vector DB** — one database to run/secure/explain instead of two; dataset scale (a few hundred doc chunks per repo) doesn't need a specialized vector store; strong, current interview topic on its own.
- **No Celery/Redis for MVP** — synchronous/async FastAPI background tasks are enough at this PR volume; a broker+worker adds a dependency to debug without a corresponding benefit yet.

## 11. Database Entities
Users, Repositories, PullRequests, Commits, ChangedFiles, PRMetrics, Predictions, ModelVersions, LLMAnalyses (+ linked RAG context), RepoDocuments, DocumentChunks/Embeddings, RetrievalLogs, RiskFactors, Recommendations, AuditLogs.

## 12. Timeline (21 phases, ~16–18 weeks, 4-person team)
Wk1-2: Ph0-1 (definition, setup). Wk3-4: Ph2-4 (DB, backend, auth). Wk5-6: Ph5-7 (GitHub, metrics). Wk7-9: Ph8-10 (dataset/labels, ML, eval). Wk10: Ph11 (LLM). Wk11-12: Ph12-14 (RAG fundamentals → pgvector → RAG-enhanced LLM). Wk13: Ph15 (hybrid engine). Wk14: Ph16 (dashboard). Wk15: Ph17-18 (testing, Docker/CI). Wk16: Ph19 (cloud deploy). Wk17-18: Ph20-21 (experiments, docs, viva prep).

## 13. Team Split
M1: Backend+GitHub API · M2: Dataset+ML+experiments · M3: Frontend+dashboard · M4: LLM+RAG+DevOps — all 4 review each other's work, weekly sync.

## 14. Risks & Mitigations
Rate limits → cache+REST batching · label noise → document, spot-check sample · imbalance → right metrics, not accuracy · irrelevant RAG retrieval → doc curation, top-K tuning · missing repo docs → choose repos with real docs/guidelines · embedding cost/latency → cache embeddings, embed once per doc version · LLM invalid output → JSON-schema validation+retry · leakage → strict chronological split · coordination → shared bible + weekly review.

## 15. Phase Log
- **Phase 0 — DONE & APPROVED**: research question, scope, methodology, RAG redesign
- **Phase 1 — DONE**: repo created, `.gitignore`/`README`/`LICENSE` (MIT) on `main`; project skeleton merged via branch `chore/project-skeleton` + PR #1
- **Phase 2 — NEXT**: PostgreSQL + schema design