import { Link, Navigate, Outlet, useNavigate } from 'react-router'
import { clearToken, getToken } from '../lib/api'
import type { Me } from '../lib/types'
import { useApi } from '../lib/useApi'

/** Header + page area for every logged-in page. No token: go to /login. */
export default function Layout() {
  if (!getToken()) return <Navigate to="/login" replace />
  return <LoggedIn />
}

function LoggedIn() {
  const navigate = useNavigate()
  const me = useApi<Me>('/users/me')

  function logout() {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link to="/" className="font-semibold text-slate-900">
            PR Risk Dashboard
          </Link>
          <div className="flex items-center gap-4 text-sm text-slate-600">
            {me.data && <span>@{me.data.github_username}</span>}
            <button onClick={logout} className="rounded-md px-2 py-1 hover:bg-slate-100">
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
