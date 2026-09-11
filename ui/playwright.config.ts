import { defineConfig, devices } from '@playwright/test'

// Overridable via PW_PORT for local runs on machines where 5173 is already bound by an
// unrelated process (e.g. another dev server); CI and the documented `make e2e` workflow are
// unaffected since PW_PORT is unset there and the default stays 5173.
const port = process.env.PW_PORT ?? '5173'
const baseURL = `http://localhost:${port}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run dev -- --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
  },
})
