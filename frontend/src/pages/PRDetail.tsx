import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { LabelBadge, LLMBadge } from '../components/badges'
import type { Hybrid, LLMAnalysis, PRDetail as PR } from '../lib/types'
import { useApi } from '../lib/useApi'

const date = (s: string | null) => (s ? new Date(s).toLocaleDateString() : '—')

export default function PRDetail() {
  const { owner, repo, number } = useParams()
  const { data: pr, error, loading } = useApi<PR>(`/repos/${owner}/${repo}/prs/${number}`)
  const back = (
    <Link to={`/repos/${owner}/${repo}`} className="text-sm text-slate-500 hover:text-slate-900">← {owner}/{repo}</Link>
  )
  if (loading) return <>{back}<p className="mt-4 text-sm text-slate-500">Loading pull request…</p></>
  if (error || !pr) return <>{back}<p className="mt-4 text-sm text-red-600">Could not load this pull request: {error}</p></>

  // The first analysis is the one the dashboard scores with (research model, current prompt, with docs).
  const main = pr.llm_analyses[0]?.use_rag ? pr.llm_analyses[0] : null
  const noDocs = pr.llm_analyses.find((a) => !a.use_rag && main && a.model === main.model && a.prompt_version === main.prompt_version)

  return (
    <article>
      {back}
      <header className="mt-2">
        <h1 className="text-xl font-semibold text-slate-900">
          <span className="text-slate-400">#{pr.number}</span> {pr.title}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          {pr.author} · {pr.state} · opened {date(pr.created_at)} · merged {date(pr.merged_at)}
          {pr.base_branch && <> · {pr.head_branch} → {pr.base_branch}</>} ·{' '}
          <a href={pr.github_url} target="_blank" rel="noreferrer" className="underline hover:text-slate-900">View on GitHub</a>
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Why the model flags it">
            {main ? <Analysis a={main} /> : <p className="text-sm text-slate-600">No LLM answer with docs is stored for this PR, so only its size can be judged.</p>}
          </Card>
          {main && main.retrieved_docs.length > 0 && (
            <Card title="Docs the LLM was shown">
              <p className="text-xs text-slate-500">The 4 sections of the project's documentation closest in meaning to this PR. Lower distance = closer match; above about 0.5 the match is often weak.</p>
              <ol className="mt-3 space-y-2">
                {main.retrieved_docs.map((d, i) => (
                  <li key={i} className="flex items-baseline justify-between gap-4 text-sm">
                    <span className="text-slate-800">{d.heading ?? '(no heading)'}</span>
                    <span className="shrink-0 tabular-nums text-slate-500">{d.distance.toFixed(3)}</span>
                  </li>
                ))}
              </ol>
            </Card>
          )}
          <Card title={`Changed files (${pr.files.length})`}>
            <table className="w-full text-sm">
              <tbody>
                {pr.files.map((f) => (
                  <tr key={f.filename} className="border-b border-slate-100 last:border-0">
                    <td className="py-1.5 pr-4 font-mono text-xs text-slate-800 break-all">{f.filename}</td>
                    <td className="py-1.5 pr-4 text-xs text-slate-500">{f.status}</td>
                    <td className="py-1.5 pr-2 text-right font-mono text-xs text-emerald-700 tabular-nums">+{f.additions}</td>
                    <td className="py-1.5 text-right font-mono text-xs text-rose-700 tabular-nums">−{f.deletions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          {pr.description && (
            <details className="rounded-xl border border-slate-200 bg-white p-5">
              <summary className="cursor-pointer text-sm font-semibold text-slate-900">PR description</summary>
              <pre className="mt-3 whitespace-pre-wrap break-words font-sans text-sm text-slate-700">{pr.description}</pre>
            </details>
          )}
        </div>

        <aside className="space-y-6">
          <Card title="Risk score">
            <HybridPanel hybrid={pr.hybrid} />
            {main && noDocs && (
              <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-600">
                Same LLM without the docs: <strong className="tabular-nums">{noDocs.risk_score}</strong> ({noDocs.risk_level})
                {' '}vs <strong className="tabular-nums">{main.risk_score}</strong> with them.
              </p>
            )}
          </Card>
          {pr.metrics && (
            <Card title="Size and history">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <Stat label="Files changed" value={pr.metrics.files_changed} />
                <Stat label="Lines changed" value={pr.metrics.churn} />
                <Stat label="Lines added" value={pr.metrics.lines_added} />
                <Stat label="Lines deleted" value={pr.metrics.lines_deleted} />
                <Stat label="Commits" value={pr.metrics.commit_count} />
                <Stat label="Test files" value={pr.metrics.test_files_changed} />
                <Stat label="Sensitive file" value={pr.metrics.is_sensitive_file ? 'yes' : 'no'} />
              </dl>
            </Card>
          )}
          <Card title="What happened later (hindsight)">
            <p className="text-xs text-slate-500">Not known when the PR was merged. Used to grade the scores, never to make them.</p>
            {pr.labels.length === 0 && <p className="mt-3 text-sm text-slate-600">No label computed.</p>}
            <ul className="mt-3 space-y-2">
              {pr.labels.map((l) => (
                <li key={l.version} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-6 text-xs text-slate-500">v{l.version}</span>
                    <LabelBadge label={l} />
                    {l.version === 3 && <span className="text-xs text-slate-400">main label</span>}
                  </div>
                  {l.reasons && l.window_complete && <p className="ml-8 mt-0.5 text-xs text-slate-500">{l.reasons} ({l.window_days} days)</p>}
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </article>
  )
}

function Analysis({ a }: { a: LLMAnalysis }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <LLMBadge llm={a} />
        <span className="text-xs text-slate-500">{a.model} · prompt v{a.prompt_version} · with project docs</span>
      </div>
      {a.diff_truncated && (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900 ring-1 ring-amber-200 ring-inset">
          The diff was too long, so the LLM saw only part of it.
        </p>
      )}
      <p className="mt-3 text-sm leading-relaxed text-slate-800">{a.summary}</p>
      {a.concerns.length > 0 && (
        <ul className="mt-4 space-y-3">
          {a.concerns.map((c, i) => (
            <li key={i} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">{c.category}</span>
                <span className="font-mono text-xs text-slate-600 break-all">{c.file}</span>
              </div>
              <p className="mt-1.5 text-sm text-slate-700">{c.explanation}</p>
            </li>
          ))}
        </ul>
      )}
      {a.tests_included !== null && (
        <p className="mt-3 text-xs text-slate-500">Tests included in the PR: {a.tests_included ? 'yes' : 'no'} (LLM's reading)</p>
      )}
    </div>
  )
}

function HybridPanel({ hybrid }: { hybrid: Hybrid | null }) {
  if (!hybrid) return <p className="text-sm text-slate-600">Not scored: the hybrid needs both the size and a stored LLM answer.</p>
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums text-slate-900">{Math.round(hybrid.score)}</span>
        <span className="text-sm text-slate-500">/ 100 hybrid</span>
        <span className="ml-auto rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-800 ring-1 ring-amber-200 ring-inset">experimental</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">Average of the two percentiles below, against {hybrid.reference_prs} analysed PRs.</p>
      <Bar label="Size (lines changed)" value={hybrid.size_percentile} />
      <Bar label="LLM + docs score" value={hybrid.llm_percentile} />
    </div>
  )
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span className="tabular-nums">percentile {Math.round(value)}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-slate-700" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="mb-3 text-sm font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  )
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium tabular-nums text-slate-900">{value ?? '—'}</dd>
    </div>
  )
}
