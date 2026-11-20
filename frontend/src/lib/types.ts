// The shapes the backend returns (backend/routes/repos.py). Keep the two in step.

export interface Repo {
  is_public: boolean // the showcase repo anyone can open, without logging in
  is_owner: boolean // the logged-in user ingested it
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

export interface Metrics {
  files_changed: number | null
  lines_added: number | null
  lines_deleted: number | null
  churn: number | null
  commit_count: number | null
  test_files_changed: number | null
  is_sensitive_file: boolean
}

/** Which later PR made a label risky (hindsight). Filled by the labelling step; older labels have none. */
/** The later pull requests that made a label risky (first revert, first fix, in merge order). */
export interface LabelEvidence {
  revert: { number: number; title: string; merged_at: string } | null
  fix: {
    number: number
    title: string
    merged_at: string
    commit_sha: string
    commit_message: string // first line only
    files: string[] // files both pull requests changed
  } | null
}

export interface LabelDetail extends Label {
  window_days: number
  reasons: string | null
  evidence: LabelEvidence | null
}

export interface Concern {
  category: string
  file: string
  explanation: string
}

export interface LLMAnalysis {
  model: string
  prompt_version: number
  use_rag: boolean
  risk_score: number
  risk_level: string
  summary: string
  concerns: Concern[]
  tests_included: boolean | null
  diff_truncated: boolean
  retrieved_docs: { heading: string | null; distance: number }[]
  created_at: string | null
}

export interface ChangedFile {
  filename: string
  status: string | null
  additions: number
  deletions: number
  has_diff: boolean
}

export interface PRDetail {
  number: number
  title: string
  description: string | null
  author: string
  state: string
  base_branch: string | null
  head_branch: string | null
  created_at: string
  merged_at: string | null
  github_url: string
  metrics: Metrics | null
  hybrid: Hybrid | null
  labels: LabelDetail[]
  llm_analyses: LLMAnalysis[]
  files: ChangedFile[]
}

/** One analysed PR on the risk map (GET /repos/{owner}/{repo}/score-map). */
export interface MapPoint {
  number: number
  title: string
  size_percentile: number
  llm_percentile: number
  score: number
  hindsight: 'fix' | 'no_fix' | 'pending' | null
}

export interface ScoreMap {
  reference_prs: number
  points: MapPoint[]
}
