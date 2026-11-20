import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('an unknown address shows a friendly 404 with ways out', async ({ page }) => {
  await page.goto('/no/such/page')
  await expect(page.getByRole('heading', { name: 'This page does not exist' })).toBeVisible()
  await expect(page).toHaveTitle('Page not found · PR Risk')
  await page.getByRole('main').getByRole('link', { name: 'The demo' }).click()
  await expect(page).toHaveURL(/\/repos\/encode\/httpx$/)
})

test('an unknown repository explains itself', async ({ page }) => {
  await page.goto('/repos/nobody/nothing')
  await expect(page.getByText('No repository here.')).toBeVisible()
})

test('every page has its own title', async ({ page }) => {
  for (const [path, title] of [
    ['/', 'PR Risk: which pull requests deserve a second look'],
    ['/repos', 'Repositories · PR Risk'],
    ['/repos/encode/httpx', 'encode/httpx · PR Risk'],
    ['/repos/encode/httpx/prs/3394', '#3394 Graceful upgrade path for 0.28. · PR Risk'],
    ['/login', 'Log in · PR Risk'],
  ]) {
    await page.goto(path)
    await expect(page).toHaveTitle(title)
  }
})

test('a new page starts at the top', async ({ page }) => {
  await page.goto('/repos/encode/httpx')
  await expect(page.locator('tbody tr')).toHaveCount(50)
  await page.mouse.wheel(0, 3000)
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(500)
  await page.locator('tbody tr td:first-child a').last().click()
  await expect(page).toHaveURL(/\/prs\/\d+$/)
  // the address changes at once; the page (and the scroll reset) follows when its code has loaded
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
})

test('no JavaScript errors on any page', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && !m.text().includes('404') && errors.push(m.text()))
  for (const path of ['/', '/repos', '/repos/encode/httpx', '/repos/encode/httpx/prs/3394', '/repos/encode/httpx/prs/3004', '/login', '/nope']) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
  }
  expect(errors).toEqual([])
})
