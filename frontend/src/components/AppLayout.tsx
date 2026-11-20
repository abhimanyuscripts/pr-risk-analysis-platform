import { Suspense } from 'react'
import { Outlet } from 'react-router'
import SiteFooter from './SiteFooter'
import SiteHeader from './SiteHeader'

/** Shell for the data pages. They are public for showcase repos; private repos need a login (the API decides). */
export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
        {/* the header stays while the next page's code arrives */}
        <Suspense fallback={<div className="h-[60vh]" aria-busy="true" />}>
          <Outlet />
        </Suspense>
      </main>
      <SiteFooter />
    </div>
  )
}
