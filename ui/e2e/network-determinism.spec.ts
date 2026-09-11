import { test, expect } from '@playwright/test'
import { installFrameworkFixtures } from './fixtures/framework-fixtures'

// `installFrameworkFixtures` mocks every app-data fetch (framework-versions.json,
// portfolio.json), but Vanilla Framework's SCSS and GlobalNav's Canonical logo/favicon still
// reference `assets.ubuntu.com` for fonts/images. Left un-mocked, the suite depends on a live
// external CDN finishing every request before a page is considered loaded — a source of CI
// flakiness (timeouts, rate limiting, transient CDN header bugs) that has nothing to do with the
// app behavior under test. This asserts the fixture helper aborts those requests before they
// ever reach the network, so the suite is fully self-contained.
test.describe('E2E fixture determinism', () => {
  test.beforeEach(async ({ page }) => {
    await installFrameworkFixtures(page)
  })

  test('never depends on network access to assets.ubuntu.com', async ({ page }) => {
    const initiated: string[] = []
    const finished: string[] = []
    const failed: string[] = []
    page.on('request', request => {
      if (request.url().includes('assets.ubuntu.com')) initiated.push(request.url())
    })
    page.on('requestfinished', request => {
      if (request.url().includes('assets.ubuntu.com')) finished.push(request.url())
    })
    page.on('requestfailed', request => {
      if (request.url().includes('assets.ubuntu.com')) failed.push(request.url())
    })

    await page.goto('/#/v0')
    await expect(page.getByRole('heading', { name: /products overview/i })).toBeVisible()
    // Wait for all network activity (not an arbitrary sleep) so late-loading font/logo requests
    // have resolved one way or another before asserting on them.
    await page.waitForLoadState('networkidle')

    // The app still references assets.ubuntu.com (logo, favicon, vanilla-framework fonts), so
    // requests are still *initiated* — this guards against the assertions below passing
    // vacuously because nothing was requested at all.
    expect(initiated.length).toBeGreaterThan(0)
    // But every one of them must be aborted at the routing layer before reaching the real CDN:
    // none may finish successfully, and all initiated requests must show up as failed (aborted).
    expect(finished).toEqual([])
    expect(failed.sort()).toEqual(initiated.sort())
  })
})
