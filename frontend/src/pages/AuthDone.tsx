import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { getToken, setToken, takeReturnPath } from '../lib/api'

/** GitHub login ends here: /auth/done#token=... (the backend puts the token after '#'). */
export default function AuthDone() {
  const navigate = useNavigate()

  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
    if (token) {
      setToken(token)
      // remove the token from the address bar and the browser history
      window.history.replaceState(null, '', window.location.pathname)
    }
    // React runs this twice in development; the second time the hash is gone, so check storage
    navigate(getToken() ? takeReturnPath() : '/login', { replace: true })
  }, [navigate])

  return <p className="p-8 text-sm text-graphite">Logging you in…</p>
}
