import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mockApi } from './mockApi'

// Automated accessibility checks (axe-core, WCAG 2.1 A and AA) on every kind of page.
// They catch contrast, missing names and wrong ARIA; they do not replace trying the site with a keyboard.
const PAGES = ['/', '/repos', '/repos/encode/httpx', '/repos/encode/httpx/prs/3394', '/login', '/no/such/page']

for (const path of PAGES) {
  test(`no accessibility violations on ${path}`, async ({ page }) => {
    await mockApi(page)
    await page.emulateMedia({ reducedMotion: 'reduce' }) // check the final state, not a frame of an animation
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    const summary = violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length}× e.g. ${v.nodes[0]?.target.join(' ')}`)
    expect(summary).toEqual([])
  })
}
