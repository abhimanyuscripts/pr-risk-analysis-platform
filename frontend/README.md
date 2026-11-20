# Frontend

React dashboard for the PR Risk platform (Phase 16c): React + TypeScript + Vite + Tailwind CSS + React Router.
It only reads stored data from the FastAPI backend (`backend/routes/repos.py`).

## Run it

1. Start the backend first (`cd backend && uvicorn main:app --reload`, port 8000).
2. Then, in another terminal:

```
cd frontend
npm install     # first time only
npm run dev     # http://localhost:5173
```

Log in with GitHub on the start page. The backend sends you back to `/auth/done` with a 60-minute token,
which the app keeps in `sessionStorage` (gone when the tab is closed).

## Settings

- `VITE_API_URL` (optional, in `.env.local`): backend address, default `http://localhost:8000`.
- The port is fixed at 5173 because the backend allows that origin (CORS) and returns there after login.

## Browser tests (Phase 17b)

Playwright opens a real Chromium, runs the built app and answers every API call itself
(`e2e/mockApi.ts`), so the backend, database and GitHub are not needed.

```
npx playwright install chromium   # first time only (downloads the browser)
npm run test:e2e
```

A failed test leaves a trace you can replay: `npx playwright show-trace test-results/<test>/trace.zip`.

## Other commands

- `npm run build`: type-check and build into `dist/`
- `npm run lint`: lint the source
