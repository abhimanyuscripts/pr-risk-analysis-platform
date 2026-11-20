import { expect, test, type Page } from '@playwright/test'
import { loginAs, MAP, mockApi, PRS, type MockApi } from './mockApi'

let api: MockApi
test.beforeEach(async ({ page }) => {
  api = await mockApi(page)
  await loginAs(page)
})

const lastQuery = () => Object.fromEntries(api.prListQueries.at(-1)!)

/** The fix ring furthest from every other point, in the middle of the map (away from the sticky header). */
function isolatedFix() {
  const dist = (a: (typeof MAP.points)[number], b: (typeof MAP.points)[number]) =>
    Math.hypot(a.size_percentile - b.size_percentile, a.llm_percentile - b.llm_percentile)
  const candidates = MAP.points.filter((p) => p.hindsight === 'fix' && p.llm_percentile > 20 && p.llm_percentile < 80)
  return candidates
    .map((p) => ({ p, gap: Math.min(...MAP.points.filter((q) => q !== p).map((q) => dist(p, q))) }))
    .sort((a, b) => b.gap - a.gap)[0].p
}
const rows = (page: Page) => page.locator('tbody tr')
const hindsight = (page: Page) => page.locator('tbody tr td:last-child')
const sortBy = (page: Page) => page.getByLabel('Sort by')
const order = (page: Page) => page.getByLabel('Order')
const filter = (page: Page) => page.getByLabel('Hindsight label')

test('default view: hybrid, highest first, 50 per page', async ({ page }) => {
  await page.goto('/repos/encode/httpx')
  await expect(page.getByText('1–50 of 120')).toBeVisible()
  await expect(rows(page)).toHaveCount(50)
  expect(lastQuery()).toEqual({ sort: 'hybrid', desc: 'true', limit: '50', offset: '0' })
  await expect(page.getByText(/experimental/).first()).toBeVisible()
})

test('PRs without a hybrid come last and say "not scored"', async ({ page }) => {
  await page.goto('/repos/encode/httpx?sort=hybrid&page=3')
  await expect(page.getByText('101–120 of 120')).toBeVisible()
  await expect(page.getByText('not scored')).toHaveCount(20)
})

test('the hindsight column shows every label state, and the open PR is marked', async ({ page }) => {
  const seen: string[] = []
  let opened = 0
  for (const p of [1, 2, 3]) {
    await page.goto(`/repos/encode/httpx?sort=merged_at&page=${p}`)
    await expect(page.locator('tbody')).not.toHaveClass(/opacity/)
    await expect(rows(page).first()).toBeVisible()
    seen.push(...(await hindsight(page).allInnerTexts()))
    opened += await page.locator('tbody tr td:first-child span span', { hasText: /^open$/ }).count()
  }
  expect(seen).toHaveLength(120)
  expect(seen.filter((t) => t === 'pending')).toHaveLength(1)
  expect(seen.filter((t) => t === '—')).toHaveLength(1)
  expect(new Set(seen)).toEqual(new Set(['fix followed', 'no fix', 'pending', '—']))
  expect(opened).toBe(1)
})

test('changing the sort asks the API and updates the URL', async ({ page }) => {
  await page.goto('/repos/encode/httpx')
  await expect(rows(page)).toHaveCount(50)
  await sortBy(page).selectOption('churn')
  await expect(page).toHaveURL(/sort=churn/)
  await expect.poll(() => lastQuery().sort).toBe('churn')
})

test('the hindsight filter shows only "fix followed" and restarts at page 1', async ({ page }) => {
  await page.goto('/repos/encode/httpx?page=2')
  await expect(rows(page)).toHaveCount(50)
  await filter(page).selectOption('true')
  await expect.poll(() => lastQuery()).toMatchObject({ risky: 'true', offset: '0' })
  await expect(page).not.toHaveURL(/page=/)
  const risky = PRS.filter((p) => p.label?.is_risky).length // 39: multiples of 3, minus one PR with no label
  await expect(page.getByText(new RegExp(`of ${risky}$`))).toBeVisible()
  for (const text of await hindsight(page).allInnerTexts()) expect(text).toBe('fix followed')
})

test('paging: next, reload, last page and back', async ({ page }) => {
  await page.goto('/repos/encode/httpx?sort=churn')
  await expect(rows(page)).toHaveCount(50)
  await page.getByRole('button', { name: 'Next' }).click()
  await expect(page.getByText('51–100 of 120')).toBeVisible()
  await expect(page).toHaveURL(/page=2/)
  expect(lastQuery()).toMatchObject({ offset: '50', sort: 'churn' })
  await page.reload()
  await expect(page.getByText('51–100 of 120')).toBeVisible()
  await page.getByRole('button', { name: 'Next' }).click()
  await expect(rows(page)).toHaveCount(20)
  await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled()
  await order(page).selectOption('asc')
  await expect.poll(() => lastQuery()).toMatchObject({ desc: 'false', offset: '0' })
  await page.goBack()
  await expect(page.getByText('101–120 of 120')).toBeVisible()
})

test('the risk map shows every analysed PR and opens one on click', async ({ page }) => {
  await page.goto('/repos/encode/httpx')
  const map = page.getByRole('img', { name: /Risk map of 390 analysed pull requests/ })
  await expect(map).toBeVisible()
  await expect(map.locator('circle')).toHaveCount(390)
  const fixes = MAP.points.filter((p) => p.hindsight === 'fix').length
  await expect(page.getByText(`A fix followed (${fixes})`)).toBeVisible()
  // a "fix followed" ring with no other PR on top of it: hollow, but it must still react to the mouse
  const ring = map.locator(`circle[data-pr="${isolatedFix().number}"]`)
  await expect(ring).toHaveAttribute('r', '5')
  await ring.hover()
  await expect(page.getByText(/^Hybrid \d+ from size \d+ and LLM \d+\. A fix followed\.$/)).toBeVisible()
  await ring.click()
  await expect(page).toHaveURL(new RegExp(`/repos/encode/httpx/prs/${isolatedFix().number}$`))
})

test('clicking a PR opens its detail page', async ({ page }) => {
  await page.goto('/repos/encode/httpx')
  const first = page.locator('tbody tr td:first-child a').first()
  const number = (await first.innerText()).split(' ')[0].slice(1)
  await first.click()
  await expect(page).toHaveURL(new RegExp(`/repos/encode/httpx/prs/${number}$`))
})
