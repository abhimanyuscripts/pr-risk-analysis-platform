import { expect, test } from '@playwright/test'
import { GOOD_TOKEN, mockApi } from './mockApi'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('a visitor who is not logged in is sent to the login page', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: 'Log in with GitHub' })).toBeVisible()
})

test('GitHub login lands on the repo list and keeps the token out of the address bar', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Log in with GitHub' }).click()
  await expect(page.getByRole('heading', { name: 'Your repositories' })).toBeVisible()
  expect(page.url()).toBe('http://localhost:5173/')
  expect(await page.evaluate(() => sessionStorage.getItem('pr-risk-token'))).toBe(GOOD_TOKEN)
  await expect(page.getByText('@abhimanyuscripts')).toBeVisible()
})

test('repo cards show the stored counts and open the PR table', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Log in with GitHub' }).click()
  const card = page.getByRole('link', { name: /encode\/httpx/ })
  await expect(card).toContainText('1,805')
  await expect(card).toContainText('390')
  await card.click()
  await expect(page).toHaveURL(/\/repos\/encode\/httpx$/)
  await expect(page.getByRole('heading', { name: 'encode/httpx' })).toBeVisible()
  await page.reload() // the token survives a reload of the tab
  await expect(page.getByRole('heading', { name: 'encode/httpx' })).toBeVisible()
})

test('an expired token sends you back to login and is cleared', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('pr-risk-token', 'expired'))
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => sessionStorage.getItem('pr-risk-token'))).toBeNull()
})

test('log out clears the token', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Log in with GitHub' }).click()
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => sessionStorage.getItem('pr-risk-token'))).toBeNull()
})
