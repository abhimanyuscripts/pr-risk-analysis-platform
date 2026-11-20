import { Link } from 'react-router'
import { DEMO_PATH, SOURCE_URL } from '../lib/config'
import Mark from './Mark'

export default function SiteFooter() {
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 text-sm text-graphite md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <p className="flex items-center gap-2.5 font-semibold text-ink">
            <Mark />
            PR Risk
          </p>
          <p className="mt-3 max-w-sm leading-relaxed">
            A final-year B.Tech project at Symbiosis University of Applied Sciences, Indore, built by a team of four.
          </p>
        </div>
        <div>
          <p className="font-medium text-ink">Explore</p>
          <ul className="mt-3 space-y-2">
            <li><Link to={DEMO_PATH} className="hover:text-ink">The encode/httpx demo</Link></li>
            <li><Link to="/repos" className="hover:text-ink">Repositories</Link></li>
            <li><a href={SOURCE_URL} className="hover:text-ink">Source code on GitHub</a></li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-ink">Built with</p>
          <p className="mt-3 leading-relaxed">
            FastAPI, PostgreSQL with pgvector, scikit-learn, Gemini with retrieval over the project's docs, React and GSAP.
          </p>
        </div>
      </div>
    </footer>
  )
}
