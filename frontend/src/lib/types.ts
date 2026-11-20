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
