import { Link, useParams } from 'react-router'

// Placeholder: the PR table is the next step of Phase 16c.
export default function PRList() {
  const { owner, repo } = useParams()
  return (
    <section>
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">← Repositories</Link>
      <h1 className="mt-2 text-lg font-semibold text-slate-900">{owner}/{repo}</h1>
      <p className="mt-2 text-sm text-slate-600">The pull request table comes in the next step.</p>
    </section>
  )
}
