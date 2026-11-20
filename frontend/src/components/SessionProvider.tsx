import { useEffect, useState, useSyncExternalStore, type ReactNode } from 'react'
import { apiGet, getToken, subscribeToken } from '../lib/api'
import { SessionContext, type Session } from '../lib/session'
import type { Me } from '../lib/types'

/** Checks the stored token once (GET /users/me) and shares the user with every page. */
export default function SessionProvider({ children }: { children: ReactNode }) {
  const token = useSyncExternalStore(subscribeToken, getToken, () => null)
  const [checked, setChecked] = useState<{ token: string; user: Me | null } | null>(null)

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    apiGet<Me>('/users/me', controller.signal, { retryAnonymously: false })
      .then((user) => setChecked({ token, user }))
      .catch(() => {
        if (!controller.signal.aborted) setChecked({ token, user: null })
      })
    return () => controller.abort()
  }, [token])

  const current = token !== null && checked?.token === token
  const session: Session = { user: current ? checked.user : null, checking: token !== null && !current }
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}
