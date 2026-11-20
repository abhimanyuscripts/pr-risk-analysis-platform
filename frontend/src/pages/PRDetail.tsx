import { Link, useParams } from 'react-router'

// Placeholder: the PR detail page ("why is this PR risky?") is the next step of Phase 16c.
export default function PRDetail() {
  const { owner, repo, number } = useParams()
  return (
    <section>
      <Link to={`/repos/${owner}/${repo}`} className="text-sm text-slate-500 hover:text-slate-900">← {owner}/{repo}</Link>
      <h1 className="mt-2 text-lg font-semibold text-slate-900">Pull request #{number}</h1>
      <p className="mt-2 text-sm text-slate-600">The detail page comes in the next step.</p>
    </section>
  )
}
