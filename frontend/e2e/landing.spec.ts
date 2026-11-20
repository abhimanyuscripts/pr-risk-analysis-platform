import { expect, test, type Page } from '@playwright/test'
import { MAP, mockApi } from './mockApi'

const fixes = MAP.points.filter((p) => p.hindsight === 'fix').length
const storyMap = (page: Page) => page.getByRole('img', { name: /Risk map of 390 pull requests read by the LLM/ })

/** The same numbers the page computes: fix rate in the top tenth by hybrid vs all known outcomes. */
function expectedRates() {
  const known = MAP.points.filter((p) => p.hindsight === 'fix' || p.hindsight === 'no_fix')
  const top = new Set([...MAP.points].sort((a, b) => b.score - a.score).slice(0, Math.round(MAP.points.length / 10)).map((p) => p.number))
  const rate = (list: typeof known) => Math.round((100 * list.filter((p) => p.hindsight === 'fix').length) / list.length)
  return { top: rate(known.filter((p) => top.has(p.number))), all: rate(known), known: known.length }
}

test.describe('with motion', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
  })

  test('hero question, the two ways in, and the demo link works', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Which pull requests deserve a second look?')
    await expect(page.getByRole('button', { name: 'Log in with GitHub' })).toBeVisible()
    await page.getByRole('link', { name: 'Open the encode/httpx demo' }).click()
    await expect(page).toHaveURL(/\/repos\/encode\/httpx$/)
  })

  test('the story builds the real risk map as you scroll', async ({ page }) => {
    const map = storyMap(page)
    await expect(map.locator('circle')).toHaveCount(390)
    // before the story starts every PR sits on the middle line and no ring is shown
    await expect(map.locator('circle[r="5"]')).toHaveCount(0)
    await page.getByRole('heading', { name: 'Rank by the hybrid' }).scrollIntoViewIfNeeded()
    await expect.poll(() => map.locator('circle[r="5"]').count(), { timeout: 10_000 }).toBe(fixes)
  })

  test('the last step states the measured result from the data', async ({ page }) => {
    const { top, all, known } = expectedRates()
    await expect(page.getByText(`In the top tenth by hybrid score, ${top}% were followed by a fix, against ${all}% of all ${known} with a known outcome.`)).toBeVisible()
  })

  test('smooth scrolling is on here and off on the dashboard', async ({ page }) => {
    await expect(page.locator('html')).toHaveClass(/lenis/)
    await page.getByRole('link', { name: 'Open the encode/httpx demo' }).click()
    await expect(page.locator('tbody tr').first()).toBeVisible()
    await expect(page.locator('html')).not.toHaveClass(/lenis/)
  })

  test('six methods compared, the hybrid on top', async ({ page }) => {
    const chart = page.locator('figure').filter({ hasText: 'ROC-AUC on 389 pull requests' })
    await expect(chart.locator('li')).toHaveCount(6)
    await expect(chart.locator('li').first()).toContainText('0.843')
  })
})

test.describe('with reduced motion', () => {
  test.use({ reducedMotion: 'reduce' })

  test('the map is already complete and nothing scrolls on its own', async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await expect(storyMap(page).locator('circle[r="5"]')).toHaveCount(fixes)
    await expect(page.locator('html')).not.toHaveClass(/lenis/)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})

test('if the map cannot load, the page says so and everything else works', async ({ page }) => {
  await mockApi(page, { scoreMapFails: true })
  await page.goto('/')
  await expect(page.getByText('The map could not be loaded. The demo has the same data.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'What the score is not' })).toBeVisible()
})
