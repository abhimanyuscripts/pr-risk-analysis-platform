import { defineConfig, devices } from '@playwright/test'

// Browser tests for the dashboard (Phase 17b). The backend is NOT needed: every test answers the
// app's API calls itself (see e2e/mockApi.ts), so no database, GitHub or LLM is involved.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    // Optional: use an already installed Chromium instead of the one `npx playwright install` downloads
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Tests run against the production build (vite preview on 5173); /api never reaches a backend.
  webServer: {
    command: 'npm run build && npx vite preview --port 5173 --strictPort',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
