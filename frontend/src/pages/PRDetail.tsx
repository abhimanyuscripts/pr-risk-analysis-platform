import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { LabelBadge, LLMBadge } from '../components/badges'
import { ErrorState, NotFoundState, Skeleton } from '../components/states'
import { useSession } from '../lib/session'
import type { Hybrid, LabelDetail, LLMAnalysis, PRDetail as PR } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useDocumentTitle } from '../lib/useDocumentTitle'

const date = (s: string | null) => (s ? new Date(s).toLocaleDateString() : '—')

export default function PRDetail() {
  const { owner, repo, number } = useParams()
  const { data: pr, error, status, loading, reload } = useApi<PR>(`/repos/${owner}/${repo}/prs/${number}`)
  const { user } = useSession()
  useDocumentTitle(pr ? `#${pr.number} ${pr.title}` : `PR #${number}`)
  const back = <Link to={`/repos/${owner}/${repo}`} className="text-sm text-graphite hover:text-ink">{owner}/{repo}</Link>
  if (loading)
    return (
      <>
        {back}
        <Skeleton className="mt-3 h-10 max-w-2xl" />
        <div className="mt-10 grid gap-6 lg:grid-cols-[1.4fr_1fr]"><Skeleton className="h-72 rounded-3xl" /><Skeleton className="h-72 rounded-3xl" /></div>
      </>
    )
  if (status === 404) return <>{back}<div className="mt-6"><NotFoundState what="pull request" loggedIn={!!user} /></div></>
  if (error || !pr) return <>{back}<div className="mt-6"><ErrorState message={error ?? 'No data came back.'} onRetry={reload} /></div></>
  const repoUrl = pr.github_url.replace(/\/pull\/\d+$/, '')

  // The first analysis is the one the dashboard scores with (research model, current prompt, with docs).
  const main = pr.llm_analyses[0]?.use_rag ? pr.llm_analyses[0] : null
  const noDocs = pr.llm_analyses.find((a) => !a.use_rag && main && a.model === main.model && a.prompt_version === main.prompt_version)

  return (
    <article>
      {back}
      <h1 className="mt-2 max-w-4xl text-4xl leading-tight font-semibold tracking-[-0.025em] text-ink">
        <span className="font-normal text-graphite">#{pr.number}</span> {pr.title}
      </h1>
      <div className="mt-5 flex flex-wrap items-end gap-x-8 gap-y-2 text-sm">
        <dl className="flex flex-wrap gap-x-8 gap-y-2">
          <Meta label="Author">{pr.author}</Meta>
          <Meta label="Opened">{date(pr.created_at)}</Meta>
          <Meta label="Merged">{pr.merged_at ? date(pr.merged_at) : pr.state}</Meta>
          {pr.base_branch && <Meta label="Branch">{pr.head_branch} into {pr.base_branch}</Meta>}
        </dl>
        <a href={pr.github_url} target="_blank" rel="noreferrer" className="text-signal underline-offset-4 hover:underline">View on GitHub</a>
      </div>

      {/* Verdict band: the model's view (left) and what happened later (right), kept visibly apart */}
      <div className="mt-10 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="risk-score" className="rounded-3xl bg-ink p-8 text-white">
          <h2 id="risk-score" className="text-sm text-white/70">Risk score</h2>
          <HybridPanel hybrid={pr.hybrid} />
          {main && noDocs && (
            <p className="mt-6 border-t border-white/15 pt-4 text-sm text-white/75">
              Same LLM without the docs: {noDocs.risk_score} ({noDocs.risk_level}) vs {main.risk_score} with them.
            </p>
          )}
        </section>
        <section aria-labelledby="hindsight" className="rounded-3xl p-8 ring-1 ring-rule ring-inset">
          <h2 id="hindsight" className="font-semibold text-ink">What happened later</h2>
          <p className="mt-1 text-sm text-graphite">Hindsight, not known at merge time. Used to grade the scores, never to make them.</p>
          {pr.labels.length === 0 && <p className="mt-5 text-sm text-graphite">No label computed.</p>}
          <ul className="mt-5 space-y-3">
            {pr.labels.map((l) => (
              <li key={l.version} className="text-sm">
                <div className="flex items-center gap-3">
                  <span className="w-6 text-graphite">v{l.version}</span>
                  <LabelBadge label={l} />
                  {l.version === 3 && <span className="text-xs text-graphite">main label</span>}
                </div>
                {l.window_complete && l.evidence && l === pr.labels[0] && (
                  <Evidence label={l} mergedAt={pr.merged_at} repoUrl={repoUrl} />
                )}
                {l.window_complete && l.evidence && l !== pr.labels[0] && (
                  <EvidenceLine label={l} main={pr.labels[0]} repoUrl={repoUrl} />
                )}
                {l.window_complete && l.reasons && !l.evidence && (
                  <p className="mt-1 ml-9 text-xs text-graphite">{l.reasons} ({l.window_days} days)</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="mt-12 grid gap-12 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-12">
          <section aria-labelledby="why">
            <h2 id="why" className="text-xl font-semibold tracking-tight text-ink">Why the model flags it</h2>
            {main ? <Analysis a={main} /> : <p className="mt-3 text-graphite">No LLM answer with docs is stored for this PR, so only its size can be judged.</p>}
          </section>

          {main && main.retrieved_docs.length > 0 && (
            <section aria-labelledby="docs">
              <h2 id="docs" className="text-xl font-semibold tracking-tight text-ink">Docs the LLM was shown</h2>
              <p className="mt-1 text-sm text-graphite">
                The sections of the project's documentation closest in meaning to this PR. Shorter bar = closer match; past about 0.5 the match is often weak.
              </p>
              <ol className="mt-5 space-y-3">
                {main.retrieved_docs.map((d, i) => (
                  <li key={i} className="grid grid-cols-[1fr_7rem] items-center gap-4 text-sm">
                    <span className="text-ink">{d.heading ?? '(no heading)'}</span>
                    <span className="flex items-center gap-2">
                      <span className="h-1 flex-1 rounded-full bg-ink/8">
                        <span className={`block h-full rounded-full ${d.distance > 0.5 ? 'bg-graphite/50' : 'bg-ink'}`} style={{ width: `${Math.min(d.distance, 1) * 100}%` }} />
                      </span>
                      <span className="w-10 text-right text-graphite">{d.distance.toFixed(3)}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {pr.description && (
            <details className="group rounded-2xl ring-1 ring-rule ring-inset">
              <summary className="cursor-pointer px-5 py-4 font-medium text-ink">PR description</summary>
              <pre className="px-5 pb-5 font-sans text-sm leading-relaxed break-words whitespace-pre-wrap text-graphite">{pr.description}</pre>
            </details>
          )}
        </div>

        <aside className="space-y-12">
          {pr.metrics && (
            <section aria-labelledby="size">
              <h2 id="size" className="text-xl font-semibold tracking-tight text-ink">Size and history</h2>
              <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5">
                <Stat label="Files changed" value={pr.metrics.files_changed} />
                <Stat label="Lines changed" value={pr.metrics.churn?.toLocaleString()} />
                <Stat label="Lines added" value={pr.metrics.lines_added?.toLocaleString()} tone="text-calm" />
                <Stat label="Lines deleted" value={pr.metrics.lines_deleted?.toLocaleString()} tone="text-fix" />
                <Stat label="Commits" value={pr.metrics.commit_count} />
                <Stat label="Test files" value={pr.metrics.test_files_changed} />
                <Stat label="Touches a sensitive file" value={pr.metrics.is_sensitive_file ? 'yes' : 'no'} />
              </dl>
            </section>
          )}
          <section aria-labelledby="files">
            <h2 id="files" className="text-xl font-semibold tracking-tight text-ink">Changed files ({pr.files.length})</h2>
            <ul className="mt-4 divide-y divide-rule/70">
              {pr.files.map((f) => (
                <li key={f.filename} className="flex items-baseline justify-between gap-4 py-2 text-xs">
                  <span className="font-mono break-all text-ink">{f.filename}</span>
                  <span className="shrink-0 font-mono">
                    <span className="text-calm">+{f.additions}</span> <span className="text-fix">−{f.deletions}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </article>
  )
}

function Analysis({ a }: { a: LLMAnalysis }) {
  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <LLMBadge llm={a} />
        <span className="text-graphite">{a.model}, prompt v{a.prompt_version}, with project docs</span>
      </div>
      {a.diff_truncated && (
        <p className="mt-4 rounded-xl bg-amber/10 px-4 py-2.5 text-sm text-amber">The diff was too long, so the LLM saw only part of it.</p>
      )}
      <p className="mt-4 max-w-[68ch] text-[17px] leading-relaxed text-ink">{a.summary}</p>
      {a.concerns.length > 0 && (
        <ul className="mt-6 space-y-4">
          {a.concerns.map((c, i) => (
            <li key={i} className="border-l-2 border-amber/60 pl-4">
              <p className="text-sm">
                <span className="font-semibold text-ink capitalize">{c.category}</span>
                <span className="ml-2 font-mono text-xs break-all text-graphite">{c.file}</span>
              </p>
              <p className="mt-1 max-w-[68ch] text-sm leading-relaxed text-graphite">{c.explanation}</p>
            </li>
          ))}
        </ul>
      )}
      {a.tests_included !== null && (
        <p className="mt-5 text-sm text-graphite">Tests included in the PR, as the LLM read it: {a.tests_included ? 'yes' : 'no'}</p>
      )}
    </div>
  )
}

function HybridPanel({ hybrid }: { hybrid: Hybrid | null }) {
  if (!hybrid) return <p className="mt-3 text-white/80">Not scored: the hybrid needs both the size and a stored LLM answer.</p>
  return (
    <div>
      <div className="mt-2 flex flex-wrap items-baseline gap-3">
        <span className="text-7xl font-semibold tracking-[-0.04em]">{Math.round(hybrid.score)}</span>
        <span className="text-white/70">/ 100 hybrid</span>
        <span className="ml-auto rounded-full px-2.5 py-0.5 text-xs text-amber-200 ring-1 ring-amber-200/50">experimental</span>
      </div>
      <p className="mt-1 text-sm text-white/70">Average of the two percentiles below, against {hybrid.reference_prs} analysed PRs.</p>
      <Bar label="Size (lines changed)" value={hybrid.size_percentile} />
      <Bar label="LLM with docs" value={hybrid.llm_percentile} />
    </div>
  )
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div className="mt-5">
      <div className="flex justify-between text-sm">
        <span className="text-white/80">{label}</span>
        <span>percentile {Math.round(value)}</span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-white/15">
        <div className="h-full rounded-full bg-white" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-graphite">{label}</dt>
      <dd className="text-ink">{children}</dd>
    </div>
  )
}

function Stat({ label, value, tone = 'text-ink' }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div>
      <dt className="text-xs text-graphite">{label}</dt>
      <dd className={`text-2xl font-semibold ${tone}`}>{value ?? '—'}</dd>
    </div>
  )
}

const daysBetween = (from: string | null, to: string) =>
  from ? Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000)) : null

function PRLink({ repoUrl, number }: { repoUrl: string; number: number }) {
  return (
    <a href={`${repoUrl}/pull/${number}`} target="_blank" rel="noreferrer" className="font-medium text-signal hover:underline">
      #{number}
    </a>
  )
}

/** The later PR (and commit) that made the main label risky, with links to GitHub. */
function Evidence({ label, mergedAt, repoUrl }: { label: LabelDetail; mergedAt: string | null; repoUrl: string }) {
  const { fix, revert } = label.evidence ?? { fix: null, revert: null }
  if (!fix && !revert) return null
  return (
    <div className="mt-3 ml-9 space-y-2 rounded-xl bg-fix/5 px-4 py-3 text-sm leading-relaxed">
      {fix && (
        <>
          <p className="text-ink">
            A fix followed in <PRLink repoUrl={repoUrl} number={fix.number} />, “{fix.title}”.
          </p>
          <p className="text-graphite">
            Merged {daysBetween(mergedAt, fix.merged_at) ?? '?'} days later. Its commit{' '}
            <a href={`${repoUrl}/commit/${fix.commit_sha}`} target="_blank" rel="noreferrer" className="font-mono text-signal hover:underline">
              {fix.commit_sha.slice(0, 7)}
            </a>{' '}
            says: <span className="text-ink">{fix.commit_message}</span>
          </p>
          {fix.files.length > 0 && (
            <p className="text-graphite">
              Both pull requests changed <span className="font-mono break-words text-ink">{fix.files.join(', ')}</span>.
            </p>
          )}
        </>
      )}
      {revert && (
        <p className="text-ink">
          Reverted by <PRLink repoUrl={repoUrl} number={revert.number} />, merged {daysBetween(mergedAt, revert.merged_at) ?? '?'} days later.
        </p>
      )}
    </div>
  )
}

/** Older label versions: one line, pointing out when they found a different PR than the main label. */
function EvidenceLine({ label, main, repoUrl }: { label: LabelDetail; main: LabelDetail; repoUrl: string }) {
  const ev = label.evidence
  if (!ev?.fix && !ev?.revert) return null
  const sameFix = ev.fix && main.evidence?.fix?.number === ev.fix.number
  return (
    <p className="mt-1 ml-9 text-xs text-graphite">
      {ev.fix && (sameFix ? 'Same fix as the main label.' : <>A fix followed in <PRLink repoUrl={repoUrl} number={ev.fix.number} />.</>)}
      {ev.revert && <> Reverted by <PRLink repoUrl={repoUrl} number={ev.revert.number} />.</>}
    </p>
  )
}
