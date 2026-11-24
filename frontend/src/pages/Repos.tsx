import { Link } from 'react-router'
import { ErrorState, Skeleton } from '../components/states'
import { startLogin } from '../lib/api'
import { DEMO_REPO } from '../lib/config'
import { useSession } from '../lib/session'
import type { Repo } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export default function Repos() {
  useDocumentTitle('Repositories')
  const { user } = useSession()
  const { data, error, loading, reload } = useApi<Repo[]>('/repos')
  const shared = data?.filter((r) => r.is_public) ?? []
  const own = data?.filter((r) => r.is_owner && !r.is_public) ?? []

  return (
    <section>
      <h1 className="text-4xl font-semibold tracking-[-0.03em] text-ink">Repositories</h1>
      <p className="mt-2 text-graphite">Stored analysis only. Nothing on these pages calls GitHub or the LLM.</p>

      {loading && (
        <div className="mt-10 space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}
      {error && <div className="mt-10"><ErrorState message={error} onRetry={reload} /></div>}

      {data && (
        <>
          <Group title="Public demo" note="Open to everyone, no login needed." repos={shared} />
          {user ? (
            <Group
              title="Private to you"
              note="Only your account can open these."
              repos={own}
              empty={
                user.can_write
                  ? 'None yet. Ingest a repository through the API and it appears here. Its scores follow once the LLM step has run offline.'
                  : `Adding your own repositories isn't open yet. This site shows one study, ${DEMO_REPO}, and the LLM step runs offline on the project team's machine.`
              }
            />
          ) : (
            <div className="mt-14 rounded-2xl px-6 py-8 ring-1 ring-rule ring-inset">
              <h2 className="text-xl font-semibold tracking-tight text-ink">Your own repositories</h2>
              <p className="mt-1 max-w-md text-sm text-graphite">
                Adding repositories isn't open to the public yet. Log in with GitHub to see any stored for your account.
              </p>
              <button onClick={() => startLogin('/repos')} className="mt-5 rounded-full bg-ink px-5 py-2 text-sm font-medium text-white hover:bg-signal">
                Log in with GitHub
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Group({ title, note, repos, empty }: { title: string; note: string; repos: Repo[]; empty?: string }) {
  if (repos.length === 0 && !empty) return null
  return (
    <div className="mt-12">
      <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
      <p className="mt-1 text-sm text-graphite">{note}</p>
      {repos.length === 0 ? (
        <p className="mt-5 text-sm text-graphite">{empty}</p>
      ) : (
        <ul className="mt-5 divide-y divide-rule border-y border-rule">
          {repos.map((r) => <RepoRow key={r.full_name} repo={r} />)}
        </ul>
      )}
    </div>
  )
}

function RepoRow({ repo: r }: { repo: Repo }) {
  const share = r.pr_count ? r.llm_analyzed_count / r.pr_count : 0
  return (
    <li>
      <Link to={`/repos/${r.owner}/${r.name}`} className="group grid gap-4 py-6 sm:grid-cols-[1fr_auto] sm:items-center">
        <div>
          <p className="text-xl font-semibold tracking-tight text-ink group-hover:text-signal">
            <span className="font-normal text-graphite">{r.owner}/</span>{r.name}
          </p>
          <p className="mt-1 text-sm text-graphite">
            Last merge {r.last_merged_at ? new Date(r.last_merged_at).toLocaleDateString() : 'none yet'}
          </p>
        </div>
        <dl className="flex gap-10 text-sm">
          <div>
            <dt className="text-graphite">Pull requests</dt>
            <dd className="text-2xl font-semibold text-ink">{r.pr_count.toLocaleString()}</dd>
          </div>
          <div className="min-w-32">
            <dt className="text-graphite">Read by the LLM</dt>
            <dd className="text-2xl font-semibold text-ink">
              {r.llm_analyzed_count.toLocaleString()}
              <span className="mt-1.5 block h-1 rounded-full bg-ink/8" aria-hidden="true">
                <span className="block h-full rounded-full bg-ink" style={{ width: `${share * 100}%` }} />
              </span>
            </dd>
          </div>
        </dl>
      </Link>
    </li>
  )
}
