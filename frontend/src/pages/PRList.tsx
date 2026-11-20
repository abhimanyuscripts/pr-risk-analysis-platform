import { Link, useParams, useSearchParams } from 'react-router'
import { HybridBar, LabelBadge, LLMBadge } from '../components/badges'
import ScoreMap from '../components/ScoreMap'
import { ErrorState, NotFoundState, Skeleton } from '../components/states'
import { useSession } from '../lib/session'
import type { PRPage, ScoreMap as ScoreMapData } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useDocumentTitle } from '../lib/useDocumentTitle'

const PAGE_SIZE = 50
const SORTS = [
  { value: 'hybrid', label: 'Hybrid score' },
  { value: 'llm_score', label: 'LLM with docs' },
  { value: 'churn', label: 'Lines changed' },
  { value: 'merged_at', label: 'Merge date' },
]

export default function PRList() {
  const { owner, repo } = useParams()
  const repoPath = `/repos/${owner}/${repo}`
  useDocumentTitle(`${owner}/${repo}`)
  const { user } = useSession()
  // Sort, filter and page live in the URL, so reload, back and shared links keep them.
  const [params, setParams] = useSearchParams()
  const sort = params.get('sort') ?? 'hybrid'
  const desc = params.get('desc') !== 'false'
  const risky = params.get('risky') ?? '' // '' = all, 'true', 'false'
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  const query = new URLSearchParams({ sort, desc: String(desc), limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) })
  if (risky) query.set('risky', risky)
  const { data, error, status, loading, reload } = useApi<PRPage>(`${repoPath}/prs?${query}`)
  const map = useApi<ScoreMapData>(`${repoPath}/score-map`)

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    }
    if (!('page' in changes)) next.delete('page') // a new sort or filter starts again at page 1
    setParams(next)
  }

  if (status === 404) {
    return (
      <section>
        <Link to="/repos" className="text-sm text-graphite hover:text-ink">Repositories</Link>
        <h1 className="mt-2 mb-8 text-4xl font-semibold tracking-[-0.025em] text-ink">{owner}/{repo}</h1>
        <NotFoundState what="repository" loggedIn={!!user} />
      </section>
    )
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const first = data && data.total > 0 ? data.offset + 1 : 0
  const last = data ? data.offset + data.items.length : 0

  return (
    <section>
      <Link to="/" className="text-sm text-graphite hover:text-ink">Repositories</Link>
      <h1 className="mt-2 text-4xl font-semibold tracking-[-0.025em] text-ink">
        <span className="font-normal text-graphite">{owner}/</span>{repo}
      </h1>

      {map.loading && (
        <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,560px)_1fr]">
          <Skeleton className="aspect-square w-full" />
          <div className="space-y-3 lg:pt-4"><Skeleton className="h-6 w-48" /><Skeleton className="h-24" /></div>
        </div>
      )}
      {map.data && map.data.points.length > 0 && (
        <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,560px)_1fr] lg:items-start">
          <ScoreMap points={map.data.points} repoPath={repoPath} />
          <MapNotes points={map.data.points} />
        </div>
      )}
      {map.data && map.data.points.length === 0 && (
        <p className="mt-10 max-w-lg rounded-2xl px-6 py-6 text-sm text-graphite ring-1 ring-rule ring-inset">
          The risk map appears once the LLM has read some of this repository's pull requests.
        </p>
      )}

      <div className="mt-14 flex flex-wrap items-end gap-4 text-sm">
        <h2 className="mr-auto text-xl font-semibold tracking-tight text-ink">All pull requests</h2>
        <Select label="Sort by" value={sort} onChange={(v) => update({ sort: v })} options={SORTS} />
        <Select
          label="Order"
          value={desc ? 'desc' : 'asc'}
          onChange={(v) => update({ desc: v === 'desc' ? null : 'false' })}
          options={[{ value: 'desc', label: 'Highest first' }, { value: 'asc', label: 'Lowest first' }]}
        />
        <Select
          label="Hindsight label"
          value={risky}
          onChange={(v) => update({ risky: v })}
          options={[{ value: '', label: 'All PRs' }, { value: 'true', label: 'Fix followed' }, { value: 'false', label: 'No fix' }]}
        />
      </div>

      {error && <div className="mt-6"><ErrorState message={error} onRetry={reload} /></div>}

      <div className="mt-4 overflow-x-auto rounded-2xl bg-surface shadow-[0_1px_0_var(--color-rule)]">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-graphite">
            <tr className="border-b border-rule">
              <th className="px-5 py-3 font-medium">Pull request</th>
              <th className="hidden px-5 py-3 font-medium md:table-cell">Merged</th>
              <th className="hidden px-5 py-3 text-right font-medium md:table-cell">Files</th>
              <th className="hidden px-5 py-3 text-right font-medium sm:table-cell">Lines</th>
              <th className="hidden px-5 py-3 font-medium sm:table-cell">LLM with docs</th>
              <th className="px-5 py-3 font-medium">Hybrid</th>
              <th className="px-5 py-3 font-medium" title="What happened in the 60 days after merging; used to grade the scores">Hindsight</th>
            </tr>
          </thead>
          <tbody className={loading ? 'opacity-50' : ''}>
            {data?.items.map((pr) => (
              <tr key={pr.number} className="border-b border-rule/70 last:border-0 hover:bg-paper/60">
                <td className="max-w-[12rem] px-5 py-3 sm:max-w-md">
                  <Link to={`${repoPath}/prs/${pr.number}`} className="block truncate text-ink hover:text-signal">
                    <span className="text-graphite">#{pr.number}</span> {pr.title}
                  </Link>
                  <span className="text-xs text-graphite">
                    {pr.author}
                    {pr.state !== 'merged' && <span className="ml-2 rounded-full bg-signal/10 px-1.5 py-px text-signal">{pr.state}</span>}
                  </span>
                </td>
                <td className="hidden px-5 py-3 whitespace-nowrap text-graphite md:table-cell">{pr.merged_at ? new Date(pr.merged_at).toLocaleDateString() : '—'}</td>
                <td className="hidden px-5 py-3 text-right md:table-cell">{pr.files_changed ?? '—'}</td>
                <td className="hidden px-5 py-3 text-right sm:table-cell">{pr.churn?.toLocaleString() ?? '—'}</td>
                <td className="hidden px-5 py-3 sm:table-cell"><LLMBadge llm={pr.llm} /></td>
                <td className="px-5 py-3"><HybridBar hybrid={pr.hybrid} /></td>
                <td className="px-5 py-3"><LabelBadge label={pr.label} /></td>
              </tr>
            ))}
            {loading && !data && Array.from({ length: 8 }, (_, i) => (
              <tr key={i} className="border-b border-rule/70">
                <td className="px-5 py-4" colSpan={7}><Skeleton className="h-5" /></td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={7} className="px-5 py-10 text-center text-graphite">No pull requests match this filter.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <nav className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-graphite">
          <span>{first.toLocaleString()}–{last.toLocaleString()} of {data.total.toLocaleString()}</span>
          {pages > 1 && (
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })} className="rounded-full px-4 py-1.5 ring-1 ring-rule hover:bg-surface disabled:opacity-40">Previous</button>
              <span className="px-2">Page {page} of {pages}</span>
              <button disabled={page >= pages} onClick={() => update({ page: String(page + 1) })} className="rounded-full px-4 py-1.5 ring-1 ring-rule hover:bg-surface disabled:opacity-40">Next</button>
            </div>
          )}
        </nav>
      )}
    </section>
  )
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-graphite">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-full bg-surface px-3.5 py-2 ring-1 ring-rule">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  )
}

/** Plain-language reading of the map, computed from the points on screen (no stored claims). */
function MapNotes({ points }: { points: ScoreMapData['points'] }) {
  const known = points.filter((p) => p.hindsight === 'fix' || p.hindsight === 'no_fix')
  const sorted = [...known].sort((a, b) => b.score - a.score)
  const top = sorted.slice(0, Math.max(1, Math.round(sorted.length / 10)))
  const rate = (list: typeof known) => (list.length ? (list.filter((p) => p.hindsight === 'fix').length / list.length) * 100 : 0)
  const topRate = rate(top)
  const allRate = rate(known)

  return (
    <div className="max-w-md lg:pt-4">
      <h2 className="text-xl font-semibold tracking-tight text-ink">Reading the map</h2>
      <p className="mt-3 leading-relaxed text-graphite">
        Each dot is a pull request the LLM has read. Right means bigger than most; up means the LLM was more worried.
        The hybrid score is the average of the two, so the top-right corner is where both signals agree.
      </p>
      {known.length > 0 && (
        <dl className="mt-8 grid grid-cols-2 gap-6 border-t border-rule pt-6">
          <div>
            <dt className="text-sm text-graphite">Fix followed, top 10% by hybrid</dt>
            <dd className="mt-1 text-4xl font-semibold tracking-tight text-fix">{topRate.toFixed(0)}%</dd>
            <dd className="text-xs text-graphite">{top.length} PRs</dd>
          </div>
          <div>
            <dt className="text-sm text-graphite">Fix followed, all analysed</dt>
            <dd className="mt-1 text-4xl font-semibold tracking-tight text-ink">{allRate.toFixed(0)}%</dd>
            <dd className="text-xs text-graphite">{known.length} PRs</dd>
          </div>
        </dl>
      )}
      <p className="mt-6 text-xs leading-relaxed text-graphite">
        The hybrid is experimental: in testing it beat size alone by a small margin. "Fix followed" is hindsight,
        known only after merging, and is shown to check the scores, not to make them.
      </p>
    </div>
  )
}
