import { useEffect } from 'react'

export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · PR Risk` : 'PR Risk: which pull requests deserve a second look'
  }, [title])
}
