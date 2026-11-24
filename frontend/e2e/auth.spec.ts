import { expect, test } from '@playwright/test'
import { GOOD_TOKEN, loginAs, mockApi, type MockApi } from './mockApi'

let api: MockApi
test.beforeEach(async ({ page }) => {
  api = await mockApi(page)
})

const token = (page: import('@playwright/test').Page) => page.evaluate(() => sessionStorage.getItem('pr-risk-token'))
const header = (page: import('@playwright/test').Page) => page.getByRole('banner')

test('a visitor reads the public demo without logging in', async ({ page }) => {
  await page.goto('/repos/encode/httpx')
  await expect(page.locator('tbody tr')).toHaveCount(50)
  await expect(header(page).getByRole('button', { name: 'Log in' })).toBeVisible()
  expect(api.requests.every((r) => r.token === null)).toBe(true)
})

test('the repositories page shows the demo, and tells visitors adding repositories is not open', async ({ page }) => {
  await page.goto('/repos')
  await expect(page.getByRole('heading', { name: 'Public demo' })).toBeVisible()
  await expect(page.getByRole('main').getByRole('link', { name: /encode\/httpx/ })).toContainText('1,805')
  await expect(page.getByRole('heading', { name: 'Your own repositories' })).toBeVisible()
  await expect(page.getByText("Adding repositories isn't open to the public yet.")).toBeVisible()
  await expect(page.getByRole('main').getByRole('button', { name: 'Log in with GitHub' })).toBeVisible()
})

test('an account that cannot write is told adding repositories is not open yet', async ({ page }) => {
  api = await mockApi(page, { reader: true })
  await loginAs(page)
  await page.goto('/repos')
  await expect(header(page).getByText('@someone-else')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Private to you' })).toBeVisible()
  await expect(page.getByText("Adding your own repositories isn't open yet.", { exact: false })).toBeVisible()
  await expect(page.getByText('Ingest a repository through the API')).toHaveCount(0)
})

test('the owner sees their private repository, without the "not open yet" note', async ({ page }) => {
  await loginAs(page)
  await page.goto('/repos')
  await expect(page.getByRole('link', { name: /pr-risk-analysis-platform/ })).toBeVisible()
  await expect(page.getByText("Adding your own repositories isn't open yet.", { exact: false })).toHaveCount(0)
})

test('logging in from a page returns to that page and keeps the token out of the address bar', async ({ page }) => {
  await page.goto('/repos/encode/httpx/prs/3394')
  await header(page).getByRole('button', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/repos\/encode\/httpx\/prs\/3394$/)
  await expect(header(page).getByText('@abhimanyuscripts')).toBeVisible()
  expect(page.url()).not.toContain('token')
  expect(await token(page)).toBe(GOOD_TOKEN)
})

test('logging in from the login page lands on your repositories', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Log in with GitHub' }).click()
  await expect(page).toHaveURL(/\/repos$/)
  await expect(page.getByRole('heading', { name: 'Private to you' })).toBeVisible()
  await expect(page.getByRole('link', { name: /pr-risk-analysis-platform/ })).toBeVisible()
  await page.reload() // the session survives a reload of the tab
  await expect(header(page).getByText('@abhimanyuscripts')).toBeVisible()
})

test('a private repository is "not here" for visitors, and opens after logging in', async ({ page }) => {
  await page.goto('/repos/abhimanyuscripts/pr-risk-analysis-platform')
  await expect(page.getByText('No repository here.')).toBeVisible()
  await page.getByRole('main').getByRole('button', { name: 'Log in with GitHub' }).click()
  await expect(page).toHaveURL(/\/repos\/abhimanyuscripts\/pr-risk-analysis-platform$/)
  await expect(page.getByText('No repository here.')).toHaveCount(0)
  await expect(page.getByText('No risk map yet.')).toBeVisible()
  await expect(page.getByText('runs offline on the project team')).toBeVisible()
})

test('an expired token is dropped quietly and the public page still loads', async ({ page }) => {
  await loginAs(page, 'expired')
  await page.goto('/repos/encode/httpx')
  await expect(page.locator('tbody tr')).toHaveCount(50)
  await expect(header(page).getByRole('button', { name: 'Log in' })).toBeVisible()
  expect(await token(page)).toBeNull()
  // the first request that sent it got a 401; everything after goes without a token
  const first = api.requests.findIndex((r) => r.token === 'expired')
  expect(first).toBeGreaterThanOrEqual(0)
  expect(api.requests.filter((r) => r.path === '/repos/encode/httpx/prs').at(-1)!.token).toBeNull()
})

test('a page request that meets an expired token is sent again without it', async ({ page }) => {
  api = await mockApi(page, { slowSession: true }) // the session check has not cleared the token yet
  await loginAs(page, 'expired')
  await page.goto('/repos/encode/httpx')
  await expect(page.locator('tbody tr')).toHaveCount(50)
  const list = api.requests.filter((r) => r.path === '/repos/encode/httpx/prs').map((r) => r.token)
  expect(list).toEqual(['expired', null]) // 401 with the token, then the same request as a visitor
})

test('log out clears the token and returns to the start page', async ({ page }) => {
  await loginAs(page)
  await page.goto('/repos')
  await header(page).getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(header(page).getByRole('button', { name: 'Log in' })).toBeVisible()
  expect(await token(page)).toBeNull()
})

test('after login the app only returns to a page on this site', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('pr-risk-after-login', '//evil.example/steal'))
  await page.goto(`/auth/done#token=${GOOD_TOKEN}`)
  await expect(page).toHaveURL(/^http:\/\/localhost:5173\/repos$/)
})

test('the login page without a token in the address goes back to login', async ({ page }) => {
  await page.goto('/auth/done')
  await expect(page).toHaveURL(/\/login$/)
})
