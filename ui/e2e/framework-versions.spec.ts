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
    await expect(page.locator('.version-selector').getByRole('combobox', { name: /framework version/i })).toHaveValue(V0.id)
    await expect(page.locator('.version-selector__meta')).toHaveText(/^Refreshed /)
  })

  test('version selector switches V0 → V1 while preserving the current sub-route', async ({ page }) => {
    await page.goto('/#/v0/products')
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible()

    const selector = page.locator('.version-selector')
    await selector.getByRole('combobox', { name: /framework version/i }).selectOption({ label: V1.label })

    await expect(page).toHaveURL(/#\/v1\/products$/)
    // Same view (Products), now scoped to v1 — not bounced back to the overview.
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible()
    await expect(selector.getByRole('combobox', { name: /framework version/i })).toHaveValue(V1.id)
    await expect(selector.locator('.version-selector__meta')).toHaveText(/^Refreshed /)
  })

  test('a V1-only product appears in V1 and is absent from V0', async ({ page }) => {
    await page.goto('/#/v0/products')
    await expect(page.getByRole('heading', { name: /^products$/i })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Orbit' })).toHaveCount(0)

    await page.goto('/#/v1/products')
    await expect(page.getByRole('link', { name: 'Orbit' })).toBeVisible()
  })

  test('switching V1 → V0 while on the V1-only product page shows explicit not-found, not a silent fallback', async ({ page }) => {
    await page.goto('/#/v1/products/orbit')
    await expect(page.getByRole('heading', { name: 'Orbit' })).toBeVisible()

    await page.locator('.version-selector').getByRole('combobox', { name: /framework version/i }).selectOption({ label: V0.label })

    // The selector preserves the sub-route by design (see "preserving the current sub-route"
    // above) — it must land on /v0/products/orbit, not silently redirect to V0's overview.
    await expect(page).toHaveURL(/#\/v0\/products\/orbit$/)
    await expect(page.getByText(/product.*orbit.*not found/i)).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Orbit' })).toHaveCount(0)
  })

  test('a direct versioned deep-link loads that version', async ({ page }) => {
    await page.goto('/#/v1/dimensions/documentation')
    await expect(page.getByRole('heading', { name: /^documentation$/i })).toBeVisible()
    const selector = page.locator('.version-selector')
    await expect(selector.getByRole('combobox', { name: /framework version/i })).toHaveValue(V1.id)
    await expect(selector.locator('.version-selector__meta')).toHaveText(/^Refreshed /)
  })

  test('upcoming and archived versions are grouped in the selector and show refreshed metadata', async ({ page }) => {
    await page.goto('/#/v0')
    const selector = page.locator('.version-selector')
    const select = selector.getByRole('combobox', { name: /framework version/i })
    const refreshLine = selector.locator('.version-selector__meta')
    await expect(select.locator('optgroup[label="Upcoming"] option', { hasText: V1.label })).toHaveCount(1)
    await expect(select.locator('optgroup[label="Archived"] option', { hasText: V_ARCHIVED.label })).toHaveCount(1)

    await select.selectOption({ label: V1.label })
    await expect(select).toHaveValue(V1.id)
    await expect(refreshLine).toHaveText(/^Refreshed /)

    await select.selectOption({ label: V_ARCHIVED.label })
    await expect(select).toHaveValue(V_ARCHIVED.id)
    await expect(refreshLine).toHaveText(/^Refreshed /)
  })

  test('the version selector and refresh timestamp fit within the viewport at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    // The selector's refresh timestamp line is the longest metadata text ("Refreshed ..."),
    // so it is the worst case for overflow.
    await page.goto('/#/v1')
    const selector = page.locator('.version-selector')
    await expect(selector.getByRole('combobox', { name: /framework version/i })).toBeVisible()
    await expect(selector.locator('.version-selector__meta')).toHaveText(/^Refreshed /)
    // Wait for the actual overview content (products table, heatmap) to finish loading, not just
    // the nav/selector — the table renders after the portfolio fetch resolves and can itself
    // widen the page (e.g. via long product/squad text), so measuring overflow before it's on
    // screen would miss layout it introduces.
    await expect(page.getByRole('heading', { name: /products overview/i })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Orbit' }).first()).toBeVisible()
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
    const selector = page.locator('.version-selector')
    // Confirms it stayed in v1 (not bounced to v0's overview).
    await expect(selector.getByRole('combobox', { name: /framework version/i })).toHaveValue(V1.id)
    await expect(selector.locator('.version-selector__meta')).toHaveText(/^Refreshed /)
  })
})
