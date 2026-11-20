import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

// The demo repository is public, so these run as a visitor who never logged in.
test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

// PR #3394 uses the real API answer for encode/httpx (e2e/fixtures/pr-3394.json).
test.describe('a fully analysed PR (#3394)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/repos/encode/httpx/prs/3394')
    await expect(page.getByRole('heading', { name: 'Why the model flags it' })).toBeVisible()
  })

  test('header: title and GitHub link', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Graceful upgrade path for 0.28.')
    await expect(page.getByRole('link', { name: 'View on GitHub' })).toHaveAttribute('href', 'https://github.com/encode/httpx/pull/3394')
  })

  test('risk score: hybrid with both parts, marked experimental', async ({ page }) => {
    const aside = page.getByRole('region', { name: 'Risk score' })
    await expect(aside).toContainText('99')
    await expect(aside).toContainText('experimental')
    await expect(aside).toContainText('percentile 98')
    await expect(aside).toContainText('percentile 100')
    await expect(aside).toContainText('390 analysed PRs')
    await expect(aside).toContainText('Same LLM without the docs: 65 (medium) vs 75 with them.')
  })

  test('LLM reasons: score, summary, concerns and the truncated-diff warning', async ({ page }) => {
    const main = page.getByRole('region', { name: 'Why the model flags it' })
    await expect(main).toContainText('75')
    await expect(main).toContainText('breaking changes for the upcoming 0.28 release')
    await expect(main.locator('li')).toHaveCount(2)
    await expect(main).toContainText('httpx/_config.py')
    await expect(main).toContainText('httpx/_api.py')
    await expect(main).toContainText('saw only part of it')
  })

  test('the 4 doc sections shown to the LLM, with distances', async ({ page }) => {
    const docs = page.getByRole('region', { name: 'Docs the LLM was shown' })
    await expect(docs.locator('ol li')).toHaveCount(4)
    await expect(docs).toContainText('0.472')
    await expect(docs).toContainText('SSL certificates')
  })

  test('metrics, files (biggest first) and the hindsight labels', async ({ page }) => {
    const size = page.getByRole('region', { name: 'Size and history' })
    for (const value of ['589', '155', '434']) await expect(size).toContainText(value)
    const files = page.getByRole('region', { name: 'Changed files (11)' })
    await expect(files.locator('li')).toHaveCount(11)
    await expect(files.locator('li span.font-mono').first()).toHaveText('docs/advanced/ssl.md')
    const later = page.getByRole('region', { name: 'What happened later' })
    await expect(later.getByText('fix followed', { exact: true })).toHaveCount(3)
  })

  test('the evidence: which later PR and commit made the label risky', async ({ page }) => {
    const later = page.getByRole('region', { name: 'What happened later' })
    await expect(later).toContainText('A fix followed in #3426, “Updating deprecated docstring Client() class”.')
    await expect(later.getByRole('link', { name: '#3426' })).toHaveAttribute('href', 'https://github.com/encode/httpx/pull/3426')
    await expect(later).toContainText('Merged 17 days later.')
    await expect(later.getByRole('link', { name: '4631c6e' })).toHaveAttribute(
      'href', 'https://github.com/encode/httpx/commit/4631c6e9427650ffaaed2845709327c1f88ae81d')
    await expect(later).toContainText('says: HOTFIX: Keyword param "proxies" is missing.')
    await expect(later).toContainText('Both pull requests changed httpx/_client.py.')
    await expect(later.getByText('Same fix as the main label.')).toHaveCount(2) // v2 and v1 found the same PR
  })

  test('the PR description is folded until clicked', async ({ page }) => {
    const line = page.getByText('SSL configuration has been significantly simplified.')
    await expect(line).toBeHidden()
    await page.getByText('PR description').click()
    await expect(line).toBeVisible()
  })
})

test('a PR with nothing stored still renders, with clear messages', async ({ page }) => {
  await page.goto('/repos/encode/httpx/prs/3004')
  await expect(page.getByText('Not scored')).toBeVisible()
  await expect(page.getByText('No LLM answer with docs is stored')).toBeVisible()
  await expect(page.getByText('No label computed.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Changed files (0)' })).toBeVisible()
  await expect(page.getByText('No label computed.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Docs the LLM was shown' })).toHaveCount(0)
})

test('an unknown PR says so and the back link returns to the table', async ({ page }) => {
  await page.goto('/repos/encode/httpx/prs/99999')
  await expect(page.getByText('No pull request here.')).toBeVisible()
  await page.getByRole('link', { name: 'encode/httpx', exact: true }).click()
  await expect(page).toHaveURL(/\/repos\/encode\/httpx$/)
})
