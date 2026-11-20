// Talks to the FastAPI backend. Every request carries the login token in the Authorization header.

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const TOKEN_KEY = 'pr-risk-token'

// sessionStorage: the token survives a page reload but is gone when the tab is closed.
// The backend also expires it after 60 minutes.
export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}
export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

/** The token is missing, expired or rejected: the app sends the user back to the login page. */
export class AuthError extends Error {}

export async function apiGet<T>(path: string): Promise<T> {
  const token = getToken()
  if (!token) throw new AuthError('Not logged in')
  const response = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (response.status === 401) {
    clearToken()
    throw new AuthError('Session expired, please log in again')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

/** Full-page jump to the backend, which sends the user to GitHub and back to /auth/done. */
export function startLogin(): void {
  window.location.href = `${API_URL}/auth/login?app=true`
}
