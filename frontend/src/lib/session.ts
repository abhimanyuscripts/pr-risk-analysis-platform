import { createContext, useContext } from 'react'
import type { Me } from './types'

export interface Session {
  user: Me | null
  /** True while a stored token is being checked with the API. */
  checking: boolean
}

export const SessionContext = createContext<Session>({ user: null, checking: false })

/** The logged-in user (or null), shared by SessionProvider. */
export function useSession(): Session {
  return useContext(SessionContext)
}
