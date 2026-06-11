import { defineConfig } from '@playwright/test';

// Smoke tests against a deployed environment. Defaults target dev; override
// with E2E_FRONTEND_BASE_URL / E2E_API_BASE_URL to point elsewhere.
// Deliberately NOT named FRONTEND_BASE_URL: direnv loads the backend's .env
// into the shell, and its FRONTEND_BASE_URL would silently retarget the tests.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  timeout: 15000,
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'dev-frontend',
      use: {
        baseURL: process.env.E2E_FRONTEND_BASE_URL || 'https://version-check.dev.devtools.site',
      },
    },
  ],
});
