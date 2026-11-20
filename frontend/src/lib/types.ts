// The shapes the backend returns (backend/routes/repos.py). Keep the two in step.

export interface Repo {
  owner: string
  name: string
  full_name: string
  pr_count: number
  last_merged_at: string | null
  llm_analyzed_count: number
}

export interface Me {
  github_username: string
  user_id: string
}

export interface Label {
  version: number
  is_risky: boolean
  window_complete: boolean // false = too recent to know; not a result yet
}

export interface LLMScore {
  risk_score: number
  risk_level: 'low' | 'medium' | 'high' | string
  use_rag: boolean
}

/** Phase 15's hybrid (experimental). Percentiles are against `reference_prs` analysed PRs of the repo. */
export interface Hybrid {
  score: number
  size_percentile: number
  llm_percentile: number
  reference_prs: number
}

export interface PRListItem {
  number: number
  title: string
  author: string
  state: string
  merged_at: string | null
  files_changed: number | null
  churn: number | null
  label: Label | null
  llm: LLMScore | null
  hybrid: Hybrid | null
}

export interface PRPage {
  total: number
  limit: number
  offset: number
  items: PRListItem[]
}
