import { useCallback, useEffect, useState } from 'react'
import { AuthError, HttpError, apiGet } from './api'

interface Result<T> {
  key: string | null // which request this result belongs to
  data: T | null
  error: string | null
  status: number | null
}

/**
 * Loads one API path. Returns the data, a readable error, the HTTP status (404 means "not here,
 * or not yours") and a retry function. Pass `skip` to wait before requesting.
 */
export function useApi<T>(path: string, { skip = false }: { skip?: boolean } = {}) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<Result<T>>({ key: null, data: null, error: null, status: null })
  const key = skip ? null : `${path}#${attempt}`

  useEffect(() => {
    if (key === null) return
    const controller = new AbortController()
    apiGet<T>(path, controller.signal)
      .then((data) => setResult({ key, data, error: null, status: 200 }))
      .catch((err: Error) => {
        if (controller.signal.aborted) return
        const status = err instanceof HttpError ? err.status : err instanceof AuthError ? 401 : null
        const message = err instanceof TypeError ? 'Could not reach the server. Check your connection and try again.' : err.message
        setResult({ key, data: null, error: message, status })
      })
    return () => controller.abort()
  }, [key, path])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  // Still loading while the stored result is for an older request (e.g. the user changed the sort).
  const loading = key !== null && result.key !== key
  return {
    data: loading ? null : result.data,
    error: loading ? null : result.error,
    status: loading ? null : result.status,
    loading,
    reload,
  }
}
