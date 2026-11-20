import { Link, useParams, useSearchParams } from 'react-router'
import { HybridBar, LabelBadge, LLMBadge } from '../components/badges'
import type { PRPage } from '../lib/types'
import { useApi } from '../lib/useApi'

const PAGE_SIZE = 50
const SORTS = [
  { value: 'hybrid', label: 'Hybrid score (experimental)' },
  { value: 'llm_score', label: 'LLM + docs score' },
  { value: 'churn', label: 'Size (lines changed)' },
  { value: 'merged_at', label: 'Merge date' },
]

export default function PRList() {
  const { owner, repo } = useParams()
  // Sort, filter and page live in the URL, so reload, back and shared links keep them.
  const [params, setParams] = useSearchParams()
  const sort = params.get('sort') ?? 'hybrid'
  const desc = params.get('desc') !== 'false'
  const risky = params.get('risky') ?? '' // '' = all, 'true', 'false'
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  const query = new URLSearchParams({ sort, desc: String(desc), limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) })
  if (risky) query.set('risky', risky)
  const { data, error, loading } = useApi<PRPage>(`/repos/${owner}/${repo}/prs?${query}`)

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    }
    if (!('page' in changes)) next.delete('page') // a new sort or filter starts again at page 1
    setParams(next)
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const first = data && data.total > 0 ? data.offset + 1 : 0
  const last = data ? data.offset + data.items.length : 0

  return (
    <section>
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">← Repositories</Link>
      <h1 className="mt-2 text-lg font-semibold text-slate-900">{owner}/{repo}</h1>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">
        The hybrid averages two percentiles: PR size and the LLM + docs score. It is <strong>experimental</strong>: in
        testing it beat size alone by only a small margin (ROC-AUC 0.843 vs 0.805). "Fix followed" is hindsight
        (a later fix touched the same files within 60 days), shown for comparison, not a prediction.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-4 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-500">Sort by</span>
          <select value={sort} onChange={(e) => update({ sort: e.target.value })} className="rounded-md border border-slate-300 bg-white px-2 py-1.5">
            {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-500">Order</span>
          <select value={desc ? 'desc' : 'asc'} onChange={(e) => update({ desc: e.target.value === 'desc' ? null : 'false' })} className="rounded-md border border-slate-300 bg-white px-2 py-1.5">
            <option value="desc">Highest first</option>
            <option value="asc">Lowest first</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-500">Hindsight label</span>
          <select value={risky} onChange={(e) => update({ risky: e.target.value })} className="rounded-md border border-slate-300 bg-white px-2 py-1.5">
            <option value="">All PRs</option>
            <option value="true">Fix followed</option>
            <option value="false">No fix</option>
          </select>
        </label>
        {data && <span className="ml-auto text-slate-500 tabular-nums">{first.toLocaleString()}–{last.toLocaleString()} of {data.total.toLocaleString()}</span>}
      </div>

      {error && <p className="mt-6 text-sm text-red-600">Could not load pull requests: {error}</p>}

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Pull request</th>
              <th className="px-4 py-2.5 font-medium">Merged</th>
              <th className="px-4 py-2.5 text-right font-medium">Files</th>
              <th className="px-4 py-2.5 text-right font-medium">Lines</th>
              <th className="px-4 py-2.5 font-medium">LLM + docs</th>
              <th className="px-4 py-2.5 font-medium">Hybrid</th>
              <th className="px-4 py-2.5 font-medium">Hindsight</th>
            </tr>
          </thead>
          <tbody className={loading ? 'opacity-50' : ''}>
            {data?.items.map((pr) => (
              <tr key={pr.number} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="max-w-md px-4 py-2.5">
                  <Link to={`/repos/${owner}/${repo}/prs/${pr.number}`} className="block truncate text-slate-900 hover:underline">
                    <span className="text-slate-400">#{pr.number}</span> {pr.title}
                  </Link>
                  <span className="text-xs text-slate-500">{pr.author}{pr.state !== 'merged' && ` · ${pr.state}`}</span>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-600">{pr.merged_at ? new Date(pr.merged_at).toLocaleDateString() : '—'}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{pr.files_changed ?? '—'}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{pr.churn?.toLocaleString() ?? '—'}</td>
                <td className="px-4 py-2.5"><LLMBadge llm={pr.llm} /></td>
                <td className="px-4 py-2.5"><HybridBar hybrid={pr.hybrid} /></td>
                <td className="px-4 py-2.5"><LabelBadge label={pr.label} /></td>
              </tr>
            ))}
            {loading && !data && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">Loading pull requests…</td></tr>
            )}
            {data && data.items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">No pull requests match.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && pages > 1 && (
        <nav className="mt-4 flex items-center justify-end gap-2 text-sm">
          <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">Previous</button>
          <span className="tabular-nums text-slate-600">Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => update({ page: String(page + 1) })} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">Next</button>
        </nav>
      )}
    </section>
  )
}
