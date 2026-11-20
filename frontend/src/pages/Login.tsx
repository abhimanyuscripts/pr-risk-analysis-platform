import { startLogin } from '../lib/api'

export default function Login() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">PR Risk Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">
          See which pull requests are most likely to need a later fix, and why.
        </p>
        <button
          onClick={startLogin}
          className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700"
        >
          Log in with GitHub
        </button>
      </div>
    </main>
  )
}
