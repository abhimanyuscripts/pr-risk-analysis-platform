import { Link, NavLink, useNavigate } from 'react-router'
import { clearToken, startLogin } from '../lib/api'
import { DEMO_PATH } from '../lib/config'
import { useSession } from '../lib/session'
import Mark from './Mark'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-2.5 py-1.5 whitespace-nowrap transition-colors sm:px-3 ${isActive ? 'bg-ink/6 text-ink' : 'text-graphite hover:text-ink'}`

export default function SiteHeader({ overlay = false }: { overlay?: boolean }) {
  const { user } = useSession()
  const navigate = useNavigate()

  function logout() {
    clearToken()
    navigate('/', { replace: true })
  }

  return (
    <header
      className={`${overlay ? 'absolute inset-x-0 top-0' : 'sticky top-0 border-b border-rule bg-paper/85 backdrop-blur'} z-30`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <Link to="/" className="flex shrink-0 items-center gap-2.5 font-semibold tracking-tight whitespace-nowrap text-ink">
          <Mark />
          PR Risk
        </Link>
        <nav aria-label="Main" className="flex items-center gap-0.5 text-sm sm:gap-1">
          <NavLink to={DEMO_PATH} className={navClass} end>
            Demo
          </NavLink>
          <NavLink to="/repos" className={navClass} end>
            Repositories
          </NavLink>
          {user ? (
            <>
              <span className="hidden px-3 text-graphite md:inline">@{user.github_username}</span>
              <button onClick={logout} className="rounded-full px-2.5 py-1.5 whitespace-nowrap text-graphite hover:text-ink sm:px-3">
                Log out
              </button>
            </>
          ) : (
            <button
              onClick={() => startLogin()}
              className="ml-1.5 rounded-full bg-ink px-4 py-1.5 font-medium whitespace-nowrap text-white transition-colors hover:bg-signal sm:ml-2"
            >
              Log in
            </button>
          )}
        </nav>
      </div>
    </header>
  )
}
