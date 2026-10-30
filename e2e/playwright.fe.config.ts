import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './tests/fe',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 60_000,
  workers: 1,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
    // In GitHub Actions, failures also appear as annotations on the run.
    ...(process.env.GITHUB_ACTIONS ? [['github'] as const] : []),
  ],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
  ],
  globalSetup: './global-setup.ts',
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173',
    cwd: '../frontend',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_MOCK: '1',
      VITE_E2E: '1',
    },
  },
})
