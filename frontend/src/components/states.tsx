import { Link } from 'react-router'
import { startLogin } from '../lib/api'

/** Grey placeholder blocks in the shape of the content that is loading. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-ink/7 motion-reduce:animate-none ${className}`} aria-hidden="true" />
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-2xl px-6 py-8 ring-1 ring-rule ring-inset">
      <p className="font-medium text-ink">This could not be loaded.</p>
      <p className="mt-1 text-sm text-graphite">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-4 rounded-full px-4 py-1.5 text-sm font-medium text-ink ring-1 ring-rule hover:bg-surface">
          Try again
        </button>
      )}
    </div>
  )
}

/** 404 from the API: the repo or PR does not exist, or it is private and the visitor is not its owner. */
export function NotFoundState({ what, loggedIn }: { what: string; loggedIn: boolean }) {
  return (
    <div className="rounded-2xl px-6 py-10 ring-1 ring-rule ring-inset">
      <p className="text-lg font-semibold text-ink">No {what} here.</p>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-graphite">
        It does not exist, or it belongs to someone else.{' '}
        {loggedIn ? 'Only the account that added a repository can open it.' : 'If it is yours, log in to see it.'}
      </p>
      <div className="mt-5 flex flex-wrap gap-3 text-sm">
        {!loggedIn && (
          <button onClick={() => startLogin()} className="rounded-full bg-ink px-4 py-1.5 font-medium text-white hover:bg-signal">
            Log in with GitHub
          </button>
        )}
        <Link to="/repos" className="rounded-full px-4 py-1.5 font-medium text-ink ring-1 ring-rule hover:bg-surface">
          See repositories
        </Link>
      </div>
    </div>
  )
}
