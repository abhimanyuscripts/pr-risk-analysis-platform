import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { AuthError, apiGet } from './api'

interface Result<T> {
  path: string | null // which path this result belongs to
  data: T | null
  error: string | null
}

/** Loads one API path; an expired login sends the user to /login. */
export function useApi<T>(path: string) {
  const navigate = useNavigate()
  const [result, setResult] = useState<Result<T>>({ path: null, data: null, error: null })

  useEffect(() => {
    let cancelled = false // ignore an answer that arrives after the page moved on
    apiGet<T>(path)
      .then((data) => !cancelled && setResult({ path, data, error: null }))
      .catch((err: Error) => {
        if (cancelled) return
        if (err instanceof AuthError) navigate('/login', { replace: true })
        else setResult({ path, data: null, error: err.message })
      })
    return () => {
      cancelled = true
    }
  }, [path, navigate])

  // Still loading while the stored result is for an older path (e.g. the user changed the sort).
  const loading = result.path !== path
  return { data: loading ? null : result.data, error: loading ? null : result.error, loading }
}
