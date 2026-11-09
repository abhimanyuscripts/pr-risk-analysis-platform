# PROJECT BIBLE
## AI-Powered Pull Request Risk Analysis & Software Engineering Intelligence Platform

*Living document — update after every phase. Last updated: Phase 9 closed, v3 label added (Nov 2026).*
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

### 4a. As implemented (Phase 8; v3 added after Phase 9) — window W = 60 days, leakage-safe (only PRs merged strictly after the one being labeled)
Signals 1 and 3 above are implemented; **signal 2 (bug-labeled issues) was tested and dropped** (see below). Labels are stored versioned in `pr_labels` (`label_version`, `window_complete`).
- **v1:** reverted (`Revert "<title>"` merged later) OR a later merged PR has a commit whose message contains fix/bug/hotfix/patch (substring) and touches any shared file.
- **v2 (working label through Phase 9):** same definition, refined: overlap ignores non-source hub files (CHANGELOG*, requirements*, LICENSE*, docs/, .github/, .md/.rst/.txt/.lock/.yml/.yaml); fix keywords match as whole words (fix, fixes, fixed, bug, hotfix) — bare "patch" dropped (HTTP PATCH, "dispatch", mock patching); `window_complete=false` when the PR's window runs past the last merge in the data (exclude from training).
- **v3 (added Nov 2026, after Phase 9):** v2 rule, but test files (TEST_PATTERNS from `routes/metrics.py`, or anything under `tests/`) are ignored when matching shared files. Reason: fix PRs usually add tests to the same test files, so test-file overlap says little about the earlier PR's code. Decided after seeing Phase 9 results, so v2 and v3 are both reported, never swapped silently. Consequence: a PR that touched only test files can be risky only through a revert. Code: `is_test_file()` in `routes/labels.py`; compute with `POST /labels/compute/{owner}/{repo}?version=3`; research scripts read `LABEL_VERSION` (default 2).
  - 1,294 usable PRs: v2 584 risky (45.1%) → v3 520 (40.2%). 64 PRs moved risky→safe, 0 safe→risky; 56 of the 64 are in 2019–2020.
  - v3 risky rate by merge year: 2019 59.2%, 2020 54.8%, 2021 33.6%, 2022 17.5%, 2023 12.3%, 2024 27.5%, 2025 0% (label shift remains, slightly smaller).
  - Size effect remains: v3 risky rate by files changed 16 / 45 / 57 / 72 / 73% (1 / 2 / 3–4 / 5–8 / 9+).
  - Test-file effect shrank but remains: within the same size band, with vs without test files — 2 files 61% vs 32%, 3–4 files 64% vs 46%, 5–8 files 78% vs 56%, 9+ files 77% vs 42% (v2: 72/72/83/91% with tests). So test-file overlap explains only part of it. Untested hypothesis: PRs touching tests are often bug fixes in active areas, followed by further fixes ("fix chains").
  - **Main label from Phase 10 onwards: v3** (decided Nov 2026); v2 is still reported alongside. Research scripts default to v3 (`DEFAULT_LABEL_VERSION` in `research/load_dataset.py`); `LABEL_VERSION=2` reproduces v2.
- **Dataset: `encode/httpx`** — 1,805 PRs (1,295 merged), 5,910 commits, 6,450 changed files, 2019-04 to 2026-03. 3 PRs by deleted users are stored as `ghost`.
- **Results:** v1 flags 920/1,295 merged PRs (71%). v2 flags 584/1,294 usable (45%); 336 v1 positives dropped. v2 risky rate by merge year: 2019 69%, 2020 61%, 2021 35%, 2022 17%, 2023 16%, 2024 28%, 2025 0%.
- **Known limitation (document in the write-up):** v2 is still activity-confounded — the rate tracks how many PRs were merged nearby (dense early years, sparse recent years), not code quality. A chronological split will therefore face a large label-prior shift; Phase 9 must report per-year results and compare against the rule-based baseline.
- **Issue-based signal — tested, infeasible:** `encode/httpx` has 925 issues, 59 real issues labeled `bug`, 0 labeled `regression`; only 1 of 59 mentions a merged PR (title/body only; comments/timeline not checked). Also points at the fix PR, not the introducing PR (= SZZ-style attribution, future scope). Not built.

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
Users, Repositories, PullRequests, Commits, ChangedFiles, PRMetrics, PRLabels (implemented; versioned), Predictions, ModelVersions, LLMAnalyses (+ linked RAG context), RepoDocuments, DocumentChunks/Embeddings, RetrievalLogs, RiskFactors, Recommendations, AuditLogs.

## 12. Timeline (21 phases, ~16–18 weeks, 4-person team)
Wk1-2: Ph0-1 (definition, setup). Wk3-4: Ph2-4 (DB, backend, auth). Wk5-6: Ph5-7 (GitHub, metrics). Wk7-9: Ph8-10 (dataset/labels, ML, eval). Wk10: Ph11 (LLM). Wk11-12: Ph12-14 (RAG fundamentals → pgvector → RAG-enhanced LLM). Wk13: Ph15 (hybrid engine). Wk14: Ph16 (dashboard). Wk15: Ph17-18 (testing, Docker/CI). Wk16: Ph19 (cloud deploy). Wk17-18: Ph20-21 (experiments, docs, viva prep).

## 13. Team Split
M1: Backend+GitHub API · M2: Dataset+ML+experiments · M3: Frontend+dashboard · M4: LLM+RAG+DevOps — all 4 review each other's work, weekly sync.

## 14. Risks & Mitigations
Rate limits → cache+REST batching · label noise → document, spot-check sample · imbalance → right metrics, not accuracy · irrelevant RAG retrieval → doc curation, top-K tuning · missing repo docs → choose repos with real docs/guidelines · embedding cost/latency → cache embeddings, embed once per doc version · LLM invalid output → JSON-schema validation+retry · leakage → strict chronological split · coordination → shared bible + weekly review.

## 15. Phase Log
- **Phase 0 — DONE & APPROVED**: research question, scope, methodology, RAG redesign
- **Phase 1 — DONE**: repo, .gitignore/README/LICENSE, skeleton merged via PR
- **Phase 2 — DONE**: PostgreSQL installed, pr_risk_dev + pr_risk_app (least privilege), 6-table schema built and merged
- **Phase 3 — DONE**: FastAPI app, SQLAlchemy connection + get_db dependency, ORM models (verified against real schema), /health/db endpoint — all merged via PR
- **Phase 4 — DONE**: GitHub OAuth login + JWT sessions (HS256, 60 min), `get_current_user` dependency, `/users/me`
- **Phase 5 — DONE**: GitHub token stored Fernet-encrypted; list repos/PRs; idempotent repo + PR ingestion
- **Phase 6 — DONE**: commit and changed-file ingestion per PR
- **Phase 7 — DONE**: traditional metrics (files changed, lines added/deleted, churn, commit count, test files changed, sensitive-file flag) in `pr_metrics`
- **Phase 8 — DONE (closed)**: pagination (PR #17) and ingestion resilience — ghost users, per-PR network-error skip, commit every 50 PRs, progress logging (PR #18); `encode/httpx` ingested (1,805 PRs, 0 failed), metrics computed; versioned risk labels v1/v2 (PR #19); issue-based signal tested and dropped (see 4a). Schema migration for `pr_labels` was applied by hand (no migration tool yet; SQL is in PR #19).
- **Phase 9 — DONE**: ML baseline on `encode/httpx`, v2 labels, window_complete = true (1,294 PRs, 584 risky). Code in `research/` (load_dataset, split, evaluate, baseline_rule, logreg, random_forest).
  - Split: chronological 70/30. Train 905 PRs (2019-04 to 2022-05, 56.2% risky); test 389 (2022-05 to 2025-12, 19.3% risky). Plus expanding yearly splits, test years 2020–2025.
  - Main-split test results: flag-everything P 0.193 / R 1.00 / F1 0.323 / AUC 0.500 · churn ≥ 23 rule P 0.459 / R 0.68 / F1 0.548 / AUC 0.817 · LogReg size-only F1 0.517 / AUC 0.799 · LogReg all 7 F1 0.490 / AUC 0.791 · Random Forest (300 trees, min_samples_leaf 5, seed 42) F1 0.525 / AUC 0.780.
  - Yearly AUC 2020–2024: rule 0.721–0.853, LogReg 0.727–0.852, RF 0.722–0.836. Learned models clearly beat the rule only in 2020. 2025 has 0 risky PRs, so it is not scored.
  - Finding: no learned model beats the churn rule on the main split; differences are small and not yet tested for significance.
  - Size confound: risky rate by files changed 19% / 51% / 63% / 76% / 85% (1 / 2 / 3–4 / 5–8 / 9+).
  - Test-file confound: within every size band, PRs touching test files are labeled risky more often (1 file: 18% vs 38%; 2 files: 33% vs 72%). test_files_changed is the top feature (LogReg weight +1.18, RF permutation importance 0.061). Likely a label artifact (fix PRs add tests to the same files, or fix chains); never report it as "tests increase risk".
  - The 0.5 cut-off over-flags on the test set because of the train/test label shift.
- **v3 label — DONE** (branch `feat/label-v3`): see 4a. Phase 9 models re-run on v3 (test 389 PRs, 17.7% risky): churn rule F1 0.522 / AUC 0.805 · LogReg all 7 F1 0.524 / AUC 0.810 · Random Forest F1 0.529 / AUC 0.767. Yearly AUC 2020–2024: rule 0.668–0.819, LogReg 0.674–0.818, RF 0.729–0.817 (learned models ahead in 2020, 2022, 2024). RF permutation importance: files_changed 0.125, all others ≈ 0. Conclusion unchanged from v2: ML ≈ size rule; differences not yet tested for significance. Comparison script: `research/compare_labels.py`.
- **Phase 10 — DONE**: evaluation depth: (1) bootstrap confidence intervals for AUC/F1 to test whether method differences are real; (2) a cut-off chosen for the label shift instead of a blind 0.5; (3) label-window sensitivity (30 / 90 days vs 60); (4) optional SHAP explanations. Report v2 and v3 side by side.
  - **Task 1 — DONE: bootstrap confidence intervals** (`research/bootstrap.py`; 1,000 resamples of the 389 test PRs, seed 42, paired comparisons). v2: rule AUC 0.817 (95% 0.765–0.863), LogReg 0.791 (0.731–0.848), RF 0.780 (0.718–0.837); LogReg − rule −0.025 (−0.067 to 0.011, ahead in 10%), RF − rule −0.036 (−0.079 to 0.005, ahead in 4%). v3: rule 0.805 (0.751–0.855), LogReg 0.810 (0.749–0.863), RF 0.767 (0.703–0.827); LogReg − rule +0.006 (−0.024 to 0.036, ahead in 63%), RF − rule −0.036 (−0.083 to 0.009, ahead in 6%). F1 95% ranges ≈ ±0.08 and overlap for all methods.
  - **Finding (tested):** no learned model is clearly better than the churn rule under either label; all methods are well above chance (AUC lower bounds ≈ 0.70). Random Forest tends to do slightly worse, but its difference range still includes 0.
  - **Task 2 — DONE: cut-off tuning** (`research/threshold.py`, v3). Training split again by time: fit 724 PRs (2019-04 to 2021-04, 55.8% risky), validation 181 (2021-04 to 2022-05, 26.0%), test 389 (17.7%). Each method's cut-off chosen for best F1 on validation. Test F1, default → tuned: churn rule 0.520 (cut 26.5 lines, 104 flagged) → 0.478 (cut 15.2, 140 flagged); LogReg 0.495 (0.5) → 0.495 (0.49); RF 0.524 (0.5, 137 flagged) → 0.514 (0.6, 110 flagged). Finding: a cut-off tuned on the most recent training data does not transfer to the test period (risky rate keeps falling: 56% → 26% → 18%); tuning made the rule worse and changed the models within noise. AUC stays the primary comparison metric; F1 is reported at default cut-offs with this caveat.
  - **Task 3 — DONE: label-window sensitivity** (`research/window_sensitivity.py`; v3 rule relabeled in memory at 30/60/90 days via the backend's own `compute_label_for_pr(window_days=...)`, nothing written to `pr_labels`). Check passed: the 60-day run reproduces the stored v3 labels (1,294 PRs, 40.2% risky) and the earlier AUCs. 30 days: 1,294 PRs, 32.0% risky (test 12.9%), AUC rule 0.788 / LogReg 0.773 / RF 0.737, LogReg − rule −0.014 (95% −0.056 to +0.027). 60 days: 1,294 PRs, 40.2% (test 17.7%), AUC 0.805 / 0.810 / 0.767, LogReg − rule +0.006 (−0.024 to +0.036). 90 days: 1,291 PRs, 43.8% (test 20.9%), AUC 0.783 / 0.794 / 0.792, LogReg − rule +0.012 (−0.024 to +0.047). Finding: the conclusion (no clear difference between ML and the size rule) holds at every window. Learned models drift slightly ahead as the window grows, but every difference range includes 0. F1 rises with the window mostly because the risky share rises, so F1 is not compared across windows.
  - **Task 4 — SKIPPED: SHAP.** Permutation importance already shows the model relies almost entirely on files_changed; SHAP would repeat it. Optional future work.
  - **Phase 10 conclusion:** on encode/httpx, 7 traditional metrics + Logistic Regression or Random Forest do not clearly beat a one-line size rule, under label v2 or v3, at 30/60/90-day windows, with confidence intervals. Size (files changed) explains most of the label. Open question for Phase 11+: does reading the code (LLM, RAG) add signal beyond size?
- **Phase 11 — IN PROGRESS**: LLM analysis (Gemini free tier).
  - **Setup:** `backend/llm/` (client, prompt, analyze, run_batch). Model `gemini-3.5-flash-lite` (≈1–2 s per PR on the free tier; `gemini-2.5-flash` is closed to new users and `gemini-3.5-flash` timed out). Explicit 120 s timeout, 2 attempts. Key in `backend/.env` only.
  - **Diffs:** new `changed_files.patch` column + `POST /github/repos/{owner}/{repo}/patches?merged_since=` (974 of 1,014 test-period files have a diff).
  - **Prompt v1:** merge-time information only (title, description, file list, diffs; largest first, cap 20,000 chars per PR / 6,000 per file); PR text treated as data (prompt-injection guard); 0–100 scoring guide. Output validated with Pydantic (risk_score, risk_level, summary, concerns, tests_included), one retry on invalid JSON, temperature 0. Every answer stored in `llm_analyses` (unique per PR + model + prompt_version + use_rag) and never requested twice. Prompt frozen before scoring; any v2 must be developed on validation-period PRs, not test PRs.
  - **Run:** all 390 test-period PRs, 0 failures; avg 1,435 tokens in / 106 out, 1.6 s; 25 diffs cut.
  - **Result (v3 labels, same 389 test PRs, `research/llm_eval.py`):** LLM ROC-AUC 0.731 vs churn rule 0.805 and LogReg 0.810. Paired bootstrap: LLM − rule −0.074 (95% −0.143 to −0.008), LLM − LogReg −0.079 (−0.155 to −0.007): the size rule is really better. Flagging medium/high: precision 0.325, recall 0.188, F1 0.239 (flags only 40 PRs). Scores compressed: 349 low / 39 medium / 1 high, 13 distinct values. Mean score risky 18.3 vs safe 9.6, so there is signal (AUC well above 0.5). Spearman with churn 0.381, with files_changed 0.403: the LLM partly tracks size but is not just size.
  - **Interpretation (hypotheses, not tested):** the label is largely mechanical (file overlap ~ size), which favours size-based methods over semantic judgment; score compression and ties limit ranking; a lite model; no repository context yet (RAG is Phase 12–14). Example of label noise the LLM handles sensibly: #3174 (docs-only, LLM score 0) is labeled risky only because it was later reverted (#3192).
  - **Note for Phase 15 (hybrid):** LLM answers exist only for test-period PRs, so a learned combiner cannot be trained on them; use a fixed, pre-declared combination or fetch LLM answers for validation-period PRs.
