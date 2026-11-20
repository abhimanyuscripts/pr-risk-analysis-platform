import { Link } from 'react-router'
import Mark from '../components/Mark'
import { startLogin } from '../lib/api'
import { DEMO_PATH, DEMO_REPO } from '../lib/config'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export default function Login() {
  useDocumentTitle('Log in')
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight text-ink">
          <Mark />
          PR Risk
        </Link>
        <h1 className="mt-10 text-3xl font-semibold tracking-[-0.02em] text-ink">Log in to see your repositories</h1>
        <p className="mt-3 leading-relaxed text-graphite">
          GitHub tells PR Risk who you are; nothing in your repositories is changed. The {DEMO_REPO} demo is open to
          everyone without logging in.
        </p>
        <button
          onClick={() => startLogin('/repos')}
          className="mt-8 w-full rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-signal"
        >
          Log in with GitHub
        </button>
        <Link to={DEMO_PATH} className="mt-3 block w-full rounded-full px-6 py-3 text-center text-sm font-semibold text-ink ring-1 ring-ink/20 hover:bg-surface">
          Open the demo instead
        </Link>
      </div>
    </main>
  )
}
