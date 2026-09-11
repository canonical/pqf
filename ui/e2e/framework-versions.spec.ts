import { test, expect } from '@playwright/test'
import { installFrameworkFixtures, V0, V1, V_ARCHIVED } from './fixtures/framework-fixtures'

test.describe('Framework version navigation', () => {
  test.beforeEach(async ({ page }) => {
    await installFrameworkFixtures(page)
  })

  test('bare root redirects to the active version (V0)', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/#\/v0$/)
    await expect(page.getByRole('heading', { name: /products overview/i })).toBeVisible()
    await expect(page.getByText(`Current framework · ${V0.label}`)).toBeVisible()
  })

  test('version selector switches V0 → V1 while preserving the current sub-route', async ({ page }) => {
    await page.goto('/#/v0/products')
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible()

    await page.getByLabel(/framework version/i).selectOption({ label: V1.label })

    await expect(page).toHaveURL(/#\/v1\/products$/)
    // Same view (Products), now scoped to v1 — not bounced back to the overview.
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible()
    await expect(page.getByText(new RegExp(`Planning against ${V1.label}`))).toBeVisible()
  })

  test('a V1-only product appears in V1 and is absent from V0', async ({ page }) => {
    await page.goto('/#/v0/products')
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Orbit' })).toHaveCount(0)

    await page.goto('/#/v1/products')
    await expect(page.getByRole('link', { name: 'Orbit' })).toBeVisible()
  })

  test('a direct versioned deep-link loads that version', async ({ page }) => {
    await page.goto('/#/v1/dimensions/documentation')
    await expect(page.getByRole('heading', { name: /^documentation$/i })).toBeVisible()
    await expect(page.getByText(new RegExp(`Planning against ${V1.label}`))).toBeVisible()
    // The version selector itself reflects v1, confirming the deep link landed in the right version.
    await expect(page.getByLabel(/framework version/i)).toHaveValue(V1.id)
  })

  test('upcoming and archived versions render their lifecycle labels', async ({ page }) => {
    await page.goto('/#/v0')
    const select = page.getByLabel(/framework version/i)
    await expect(select.locator('optgroup[label="Upcoming"] option', { hasText: V1.label })).toHaveCount(1)
    await expect(select.locator('optgroup[label="Archived"] option', { hasText: V_ARCHIVED.label })).toHaveCount(1)

    await select.selectOption({ label: V1.label })
    await expect(page.getByText(new RegExp(`Planning against ${V1.label}`))).toBeVisible()

    await select.selectOption({ label: V_ARCHIVED.label })
    await expect(page.getByText(/Archived snapshot · generated/)).toBeVisible()
  })

  test('the version selector and context label fit within the viewport at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    // The upcoming-status label is the longest ("Planning against ... · refreshed YYYY-MM-DD"),
    // so it is the worst case for overflow.
    await page.goto('/#/v1')
    await expect(page.getByLabel(/framework version/i)).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })

  test('no link to the retired /legacy/ static build appears anywhere in the nav', async ({ page }) => {
    await page.goto('/#/v0')
    // Wait for the real nav (not an error/loading state) so this checks the fully rendered page.
    await expect(page.getByRole('link', { name: 'Overview' })).toBeVisible()
    const hrefs = await page.locator('a[href]').evaluateAll(anchors => anchors.map(a => a.getAttribute('href')))
    expect(hrefs.length).toBeGreaterThan(0)
    expect(hrefs.some(href => href?.includes('/legacy'))).toBe(false)
  })

  test('an unknown framework version renders explicit recovery, not a silent fallback', async ({ page }) => {
    await page.goto('/#/does-not-exist/products')
    await expect(page.getByRole('heading', { name: /framework version not found/i })).toBeVisible()
    const recoveryLink = page.getByRole('link', { name: new RegExp(`go to the active framework version.*${V0.label}`, 'i') })
    await expect(recoveryLink).toBeVisible()

    await recoveryLink.click()
    await expect(page).toHaveURL(/#\/v0$/)
    await expect(page.getByRole('heading', { name: /products overview/i })).toBeVisible()
  })

  test('an unknown sub-route under a valid version redirects back to that version\'s root', async ({ page }) => {
    await page.goto('/#/v1/this-does-not-exist')
    await expect(page).toHaveURL(/#\/v1$/)
    await expect(page.getByRole('heading', { name: /products overview/i })).toBeVisible()
    // Confirms it stayed in v1 (not bounced to v0's overview).
    await expect(page.getByText(new RegExp(`Planning against ${V1.label}`))).toBeVisible()
  })
})
