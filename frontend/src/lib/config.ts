/** The public showcase repository (must also be in the backend's PUBLIC_REPOS). */
export const DEMO_REPO: string = import.meta.env.VITE_DEMO_REPO ?? 'encode/httpx'
export const DEMO_PATH = `/repos/${DEMO_REPO}`
export const SOURCE_URL = 'https://github.com/abhimanyuscripts/pr-risk-analysis-platform'
