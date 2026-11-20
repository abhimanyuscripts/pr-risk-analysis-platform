import { Link } from 'react-router'
import type { Repo } from '../lib/types'
import { useApi } from '../lib/useApi'

export default function Repos() {
  const { data, error, loading } = useApi<Repo[]>('/repos')

  if (loading) return <p className="text-sm text-slate-500">Loading repositories…</p>
  if (error) return <p className="text-sm text-red-600">Could not load repositories: {error}</p>
  if (!data || data.length === 0)
    return <p className="text-sm text-slate-600">No repositories yet. Ingest one through the API first.</p>

  return (
    <section>
      <h1 className="text-lg font-semibold text-slate-900">Your repositories</h1>
      <p className="mt-1 text-sm text-slate-600">Stored data only; nothing here calls GitHub or the LLM.</p>
      <ul className="mt-6 grid gap-4 sm:grid-cols-2">
        {data.map((r) => (
          <li key={r.full_name}>
            <Link
              to={`/repos/${r.owner}/${r.name}`}
              className="block rounded-xl border border-slate-200 bg-white p-5 hover:border-slate-400"
            >
              <p className="font-medium text-slate-900">{r.full_name}</p>
              <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                <Stat label="PRs" value={r.pr_count.toLocaleString()} />
                <Stat label="LLM-analysed" value={r.llm_analyzed_count.toLocaleString()} />
                <Stat label="Last merge" value={r.last_merged_at ? new Date(r.last_merged_at).toLocaleDateString() : '—'} />
              </dl>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900 tabular-nums">{value}</dd>
    </div>
  )
}
