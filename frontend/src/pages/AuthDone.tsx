import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { getToken, setToken } from '../lib/api'

/** GitHub login ends here: /auth/done#token=... (the backend puts the token after '#'). */
export default function AuthDone() {
  const navigate = useNavigate()

  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
    if (token) {
      setToken(token)
      // remove the token from the address bar and browser history
      window.history.replaceState(null, '', window.location.pathname)
    }
    // React runs this twice in development; the second time the hash is already gone, so check storage
    navigate(getToken() ? '/' : '/login', { replace: true })
  }, [navigate])

  return <p className="p-8 text-sm text-slate-500">Logging you in…</p>
}
