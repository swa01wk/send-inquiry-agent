import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
const slowMo = Number(process.env.E2E_SLOW_MO ?? 0)

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.E2E_LIVE ? 1 : 0,
  timeout: 90_000,
  workers: 1,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
    ...(process.env.E2E_LIVE ? [['./reporters/liveSummary.ts'] as const] : []),
  ],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...(slowMo > 0 ? { launchOptions: { slowMo } } : {}),
  },
  projects: [
    { name: 'desktop-chrome', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
  ],
  globalSetup: './global-setup.ts',
  webServer: [
    {
      command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
      env: {
        AGENT_MODE: process.env.E2E_LIVE ? 'openai' : 'scripted',
        // verifyEmail() clicks the card's demo link button, which needs the token in the card
        EMAIL_LINK_DEMO: 'true',
        DEV_TOOLS: 'true',
        REVIEWER_CONSOLE: 'true',
        CALLCENTRE_CONSOLE: 'true',
        TENANT_PORTAL: 'true',
        PUBLIC_BASE_URL: 'http://127.0.0.1:5173',
        CORS_ORIGINS: 'http://localhost:5173,http://127.0.0.1:5173',
        RATE_LIMIT_IP: '1000/minute',
        RATE_LIMIT_SESSION: '1000/minute',
        ...(process.env.OPENAI_API_KEY ? { OPENAI_API_KEY: process.env.OPENAI_API_KEY } : {}),
        ...(process.env.OPENAI_MODEL ? { OPENAI_MODEL: process.env.OPENAI_MODEL } : {}),
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: '../frontend',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      env: {
        VITE_E2E: '1',
        VITE_DEV_TOOLS: '1',
        VITE_REVIEWER_CONSOLE: '1',
        VITE_CALLCENTRE_CONSOLE: '1',
        VITE_TENANT_PORTAL: '1',
        VITE_API_BASE: 'http://127.0.0.1:8000',
      },
    },
  ],
})
