import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router'
import AppLayout from './components/AppLayout'
import SessionProvider from './components/SessionProvider'
import AuthDone from './pages/AuthDone'

// Each page is its own download, so the dashboard never loads the start page's animation code.
const Landing = lazy(() => import('./pages/Landing'))
const Login = lazy(() => import('./pages/Login'))
const NotFound = lazy(() => import('./pages/NotFound'))
const PRDetail = lazy(() => import('./pages/PRDetail'))
const PRList = lazy(() => import('./pages/PRList'))
const Repos = lazy(() => import('./pages/Repos'))

/** A new page starts at the top (query-string changes, like sorting, keep the position). */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <ScrollToTop />
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/auth/done" element={<AuthDone />} />
            <Route element={<AppLayout />}>
              <Route path="/repos" element={<Repos />} />
              <Route path="/repos/:owner/:repo" element={<PRList />} />
              <Route path="/repos/:owner/:repo/prs/:number" element={<PRDetail />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </SessionProvider>
    </BrowserRouter>
  )
}
