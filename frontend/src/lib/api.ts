// Talks to the FastAPI backend. The API lives under /api on the same site (Vite proxies it in
// development), so there is no separate API address to configure and no CORS in production.

export const API_URL: string = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')

const TOKEN_KEY = 'pr-risk-token'
const RETURN_KEY = 'pr-risk-after-login'

// sessionStorage: the token survives a reload but is gone when the tab closes. The backend
// also expires it after 60 minutes. Components subscribe so a login or logout shows everywhere.
const listeners = new Set<() => void>()
export function subscribeToken(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
const notify = () => listeners.forEach((listener) => listener())

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}
export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
  notify()
}
export function clearToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable: nothing to clear */
  }
  notify()
}

/** The token was rejected (expired or invalid). */
export class AuthError extends Error {}

/** Any other non-2xx answer, with the HTTP status and the API's own message. */
export class HttpError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * GET an API path. When the stored token is rejected (it expired), it is removed and the request
 * is sent once more without it, so public pages keep working and the app shows "Log in" again.
 */
export async function apiGet<T>(path: string, signal?: AbortSignal, { retryAnonymously = true } = {}): Promise<T> {
  const token = getToken()
  let response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  })
  if (response.status === 401 && token) {
    clearToken()
    if (retryAnonymously) response = await fetch(`${API_URL}${path}`, { signal })
  }
  if (response.status === 401) {
    throw new AuthError('Your session has ended. Log in again to continue.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new HttpError(response.status, body?.detail ?? `The server answered ${response.status}.`)
  }
  return response.json() as Promise<T>
}

/** Full-page jump to the backend, which sends the user to GitHub and back to /auth/done. */
export function startLogin(returnTo: string = window.location.pathname + window.location.search): void {
  try {
    sessionStorage.setItem(RETURN_KEY, returnTo === '/login' ? '/repos' : returnTo)
  } catch {
    /* the app falls back to /repos */
  }
  window.location.href = `${API_URL}/auth/login?app=true`
}

/** Where to go after login: the page the user started from, once. */
export function takeReturnPath(): string {
  try {
    const path = sessionStorage.getItem(RETURN_KEY)
    sessionStorage.removeItem(RETURN_KEY)
    return path && path.startsWith('/') && !path.startsWith('//') ? path : '/repos'
  } catch {
    return '/repos'
  }
}
