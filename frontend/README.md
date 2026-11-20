# Frontend

The PR Risk website: React + TypeScript + Vite + Tailwind CSS + React Router, with GSAP and Lenis for the
scroll story on the start page. It only reads stored data from the FastAPI backend
(`backend/routes/repos.py`), always on relative `/api/...` paths.

Pages: `/` start page (the risk map built step by step as you scroll, results, method, limits),
`/repos`, `/repos/:owner/:repo` (risk map + PR table), `/repos/:owner/:repo/prs/:number` (one PR, with the
later fix that made it risky), `/login`, and a 404 page. The demo repository is public; your own
repositories appear after GitHub login.

## Run it

1. Start the backend first (`cd backend && uvicorn main:app --reload`, port 8000).
2. Then, in another terminal:

```
cd frontend
npm install     # first time only
npm run dev     # http://localhost:5173 (Vite forwards /api to the backend)
```

GitHub login returns to `/auth/done` with a 60-minute token, which the app keeps in `sessionStorage` (gone
when the tab is closed). An expired token is dropped and the request is repeated without it, so public
pages keep working.

## Motion

One orchestrated moment per page: the headline on load, and the risk map that builds itself as the start
page scrolls (GSAP ScrollTrigger, smooth scrolling with Lenis on that page only). With the system setting
"reduce motion" the page shows the finished map and scrolls normally. Each page is its own download, so the
dashboard never loads the animation code.

## Settings (optional, in `.env.local`)

- `VITE_API_URL`: only to call an API on another address (default: `/api` on the same site).
- `VITE_DEMO_REPO`: the public demo repository (default `encode/httpx`; must be in the backend's `PUBLIC_REPOS`).

## Browser tests

Playwright opens a real Chromium, runs the production build and answers every `/api` call itself
(`e2e/mockApi.ts`), so the backend, database and GitHub are not needed. The PR #3394 answer and the risk
map in `e2e/fixtures/` are saved from the real API. `e2e/a11y.spec.ts` runs axe-core (WCAG 2.1 AA) on
every kind of page.

```
npx playwright install chromium   # first time only (downloads the browser)
npm run test:e2e
```

A failed test leaves a trace you can replay: `npx playwright show-trace test-results/<test>/trace.zip`.

## Other commands

- `npm run build`: type-check and build into `dist/`
- `npm run lint`: lint the source
