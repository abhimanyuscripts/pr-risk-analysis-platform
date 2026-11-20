// A stand-in for the FastAPI backend: same paths (/api/...), response shapes and access rules, fixed data.
// Requests to /api never leave the browser; this file answers them.
//   - encode/httpx is the public demo: anyone may read it.
//   - abhimanyuscripts/pr-risk-analysis-platform is private to the logged-in user.
//   - A token other than GOOD_TOKEN is "expired": every endpoint answers 401 to it, like the real API.
import type { Page, Route } from '@playwright/test'
import pr3394 from './fixtures/pr-3394.json' with { type: 'json' }
import realMap from './fixtures/score-map-httpx.json' with { type: 'json' }

export const GOOD_TOKEN = 'good-token'

const DEMO = { owner: 'encode', name: 'httpx', full_name: 'encode/httpx', pr_count: 1805, last_merged_at: '2026-02-23T16:10:42+05:30', llm_analyzed_count: 390, is_public: true }
const PRIVATE = { owner: 'abhimanyuscripts', name: 'pr-risk-analysis-platform', full_name: 'abhimanyuscripts/pr-risk-analysis-platform', pr_count: 17, last_merged_at: '2026-09-28T10:58:29+05:30', llm_analyzed_count: 0, is_public: false }

/** 120 PRs. Every 4th has no LLM answer (so no hybrid); PR 3005 is "pending", 3007 is open, 3009 has no label. */
export const PRS = Array.from({ length: 120 }, (_, i) => {
  const n = i + 1
  const analysed = n % 4 !== 0
  const churn = [3, 10, 40, 120, 600, 2400][n % 6]
  const llmScore = (n * 7) % 90
  return {
    number: 3000 + n,
    title: `Change number ${n}`,
    author: 'dev',
    state: n === 7 ? 'open' : 'merged',
    merged_at: n === 7 ? null : `2024-${String(1 + (n % 12)).padStart(2, '0')}-${String(1 + (n % 27)).padStart(2, '0')}T10:00:00+05:30`,
    files_changed: 1 + Math.floor(churn / 100),
    churn,
    label: n === 9 ? null : { version: 3, is_risky: n % 3 === 0, window_complete: n !== 5 },
    llm: analysed ? { risk_score: llmScore, risk_level: ['low', 'medium', 'high'][Math.floor(llmScore / 34)], use_rag: true } : null,
    hybrid: analysed ? { score: ((n * 37) % 100) + 0.4, size_percentile: 50, llm_percentile: 40, reference_prs: 90 } : null,
  }
})

/** The real encode/httpx risk map, saved from the API: 390 PRs with their percentiles and hindsight. */
export const MAP = realMap as {
  reference_prs: number
  points: { number: number; title: string; size_percentile: number; llm_percentile: number; score: number; hindsight: 'fix' | 'no_fix' | 'pending' | null }[]
}

type PR = (typeof PRS)[number]
const SORT_KEYS: Record<string, (p: PR) => number | string | null> = {
  hybrid: (p) => p.hybrid?.score ?? null,
  llm_score: (p) => p.llm?.risk_score ?? null,
  churn: (p) => p.churn,
  merged_at: (p) => p.merged_at,
}

const DETAILS: Record<string, unknown> = {
  '3394': pr3394,
  '3004': {
    number: 3004, title: 'Tiny docs fix', description: null, author: 'dev', state: 'open', base_branch: null, head_branch: null,
    created_at: '2024-01-01T10:00:00+05:30', merged_at: null, github_url: 'https://github.com/encode/httpx/pull/3004',
    metrics: null, hybrid: null, labels: [], llm_analyses: [], files: [],
  },
}

export interface MockApi {
  /** Query strings the app sent to the PR list endpoint, oldest first. */
  prListQueries: URLSearchParams[]
  /** Every API path the app asked for, with whether it sent a token. */
  requests: { path: string; token: string | null }[]
}

export interface MockOptions {
  /** Make the start page's risk map fail, to check the page still works. */
  scoreMapFails?: boolean
  /** Answer /users/me late, so page requests go out while an expired token is still stored. */
  slowSession?: boolean
}

export async function mockApi(page: Page, options: MockOptions = {}): Promise<MockApi> {
  const state: MockApi = { prListQueries: [], requests: [] }
  const json = (route: Route, status: number, body: unknown) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace(/^\/api/, '')
    const token = request.headers()['authorization']?.replace(/^Bearer /, '') ?? null
    state.requests.push({ path, token })

    // Login: the real backend sends the browser to GitHub and back; here we jump straight back.
    if (path === '/auth/login' && url.searchParams.get('app') === 'true') {
      return route.fulfill({ status: 302, headers: { location: `${url.origin}/auth/done#token=${GOOD_TOKEN}` } })
    }
    if (path === '/users/me' && options.slowSession) await new Promise((resolve) => setTimeout(resolve, 1500))
    if (token !== null && token !== GOOD_TOKEN) return json(route, 401, { detail: 'Invalid or expired token' })
    const loggedIn = token === GOOD_TOKEN

    if (path === '/users/me') {
      return loggedIn ? json(route, 200, { github_username: 'abhimanyuscripts', user_id: 'u1' }) : json(route, 401, { detail: 'Missing or invalid authorization header' })
    }
    if (path === '/repos') {
      return json(route, 200, loggedIn ? [{ ...DEMO, is_owner: true }, { ...PRIVATE, is_owner: true }] : [{ ...DEMO, is_owner: false }])
    }
    if (path.startsWith('/repos/abhimanyuscripts/pr-risk-analysis-platform')) {
      if (!loggedIn) return json(route, 404, { detail: 'Repository not found' })
      if (path.endsWith('/score-map')) return json(route, 200, { reference_prs: 0, points: [] })
      if (path.endsWith('/prs')) return json(route, 200, { total: 0, limit: 50, offset: 0, items: [] })
    }
    if (path === '/repos/encode/httpx/score-map') {
      return options.scoreMapFails ? json(route, 500, { detail: 'Internal Server Error' }) : json(route, 200, MAP)
    }
    if (path === '/repos/encode/httpx/prs') {
      const q = url.searchParams
      state.prListQueries.push(q)
      const key = SORT_KEYS[q.get('sort') ?? 'merged_at']
      const desc = q.get('desc') !== 'false'
      const rows = PRS.filter((p) => !q.has('risky') || (p.label !== null && p.label.is_risky === (q.get('risky') === 'true')))
      const withValue = rows.filter((p) => key(p) !== null)
      withValue.sort((a, b) => ((key(a)! > key(b)! ? 1 : -1) * (desc ? -1 : 1)))
      const ordered = [...withValue, ...rows.filter((p) => key(p) === null)] // empty values last, like the API
      const offset = Number(q.get('offset') ?? 0)
      const limit = Number(q.get('limit') ?? 50)
      return json(route, 200, { total: ordered.length, limit, offset, items: ordered.slice(offset, offset + limit) })
    }
    const detail = path.match(/^\/repos\/encode\/httpx\/prs\/(\d+)$/)
    if (detail) {
      const body = DETAILS[detail[1]]
      return body ? json(route, 200, body) : json(route, 404, { detail: 'Pull request not found' })
    }
    return json(route, 404, { detail: 'Repository not found' })
  })
  return state
}

/** Start a test already logged in (the token the app would have stored after GitHub login). */
export async function loginAs(page: Page, token = GOOD_TOKEN): Promise<void> {
  await page.addInitScript((t) => sessionStorage.setItem('pr-risk-token', t), token)
}
