import { test, expect } from '@playwright/test'
import { installFrameworkFixtures } from './fixtures/framework-fixtures'

test.describe('PQF navigation smoke tests', () => {
  test.beforeEach(async ({ page }) => {
    await installFrameworkFixtures(page)
  })

  test('homepage redirects to the active framework version and shows the overview', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/#\/v0$/)
    await expect(page.getByRole('heading', { name: /products overview/i })).toBeVisible()
  })

  test('About page loads within the active framework version', async ({ page }) => {
    await page.goto('/#/v0/about')
    await expect(page.getByRole('heading', { name: /about pqf/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: /medal levels/i })).toBeVisible()
  })

  // An unversioned/invalid path segment is indistinguishable from an unknown framework version
  // id — the router must surface an explicit recovery state, never silently fall back to the
  // homepage with no explanation (that would hide a broken/missing version link).
  test('an invalid top-level route renders explicit framework-version recovery, not a silent homepage fallback', async ({
    page,
  }) => {
    await page.goto('/#/this-does-not-exist')
    await expect(page.getByRole('heading', { name: /framework version not found/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /go to the active framework version/i })).toBeVisible()
  })

  test('nav links are present within a framework version', async ({ page }) => {
    await page.goto('/#/v0')
    await expect(page.getByRole('link', { name: 'Overview' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Products' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Dimensions' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'About' })).toBeVisible()
  })
})
