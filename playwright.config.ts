import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  timeout: 10000, // 10 seconds
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'dev-frontend',
      use: {
        baseURL: 'https://version-check.dev.devtools.site',
      },
    },
  ],
});
