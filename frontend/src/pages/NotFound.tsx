import { Link } from 'react-router'
import { DEMO_PATH } from '../lib/config'
import { useDocumentTitle } from '../lib/useDocumentTitle'

export default function NotFound() {
  useDocumentTitle('Page not found')
  return (
    <section className="py-16">
      <p className="text-sm text-graphite">Error 404</p>
      <h1 className="mt-3 text-5xl font-semibold tracking-[-0.03em] text-ink">This page does not exist</h1>
      <p className="mt-4 max-w-md leading-relaxed text-graphite">
        The address may have a typo, or the page was moved. These are the places most people are looking for:
      </p>
      <div className="mt-8 flex flex-wrap gap-3 text-sm">
        <Link to="/" className="rounded-full bg-ink px-5 py-2 font-medium text-white hover:bg-signal">Start page</Link>
        <Link to={DEMO_PATH} className="rounded-full px-5 py-2 font-medium text-ink ring-1 ring-rule hover:bg-surface">The demo</Link>
        <Link to="/repos" className="rounded-full px-5 py-2 font-medium text-ink ring-1 ring-rule hover:bg-surface">Repositories</Link>
      </div>
    </section>
  )
}
