// Results from the research phases, shown on the start page. Source: docs/PROJECT_BIBLE.md
// (Phases 9-15 and 20a; encode/httpx, label v3, 60-day window, 389 test PRs). Change only when the research changes.

export interface MethodResult {
  name: string
  detail: string
  auc: number
  kind: 'rule' | 'ml' | 'llm' | 'hybrid'
}

export const TEST_PRS = 389
export const RISKY_SHARE = 17.7 // % of test PRs a fix followed

export const RESULTS: MethodResult[] = [
  { name: 'Hybrid', detail: 'size + LLM with docs', auc: 0.843, kind: 'hybrid' },
  { name: 'Logistic regression', detail: '7 PR metrics', auc: 0.81, kind: 'ml' },
  { name: 'Size rule', detail: 'lines changed', auc: 0.805, kind: 'rule' },
  { name: 'Random forest', detail: '7 PR metrics', auc: 0.767, kind: 'ml' },
  { name: 'LLM with docs', detail: 'Gemini + project docs (RAG)', auc: 0.763, kind: 'llm' },
  { name: 'LLM alone', detail: 'Gemini reads the diff', auc: 0.731, kind: 'llm' },
]

/** Paired bootstrap, 1,000 resamples: hybrid minus size rule. */
export const HYBRID_GAIN = { mean: 0.039, low: 0.002, high: 0.076 }

/** Phase 20a: the same 390 PRs asked again (same prompt and docs, temperature 0). */
export const NOISE_CHECK = {
  changedScores: 21.8, // % of PRs whose score changed in the second run
  gain: { mean: 0.032, low: -0.009, high: 0.071 }, // hybrid minus size rule with the second run's scores
}
