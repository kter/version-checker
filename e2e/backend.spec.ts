import { test, expect } from '@playwright/test';

test.describe('Version Checker Backend API', () => {
  const baseURL = process.env.API_BASE_URL || 'https://api.version-check.dev.devtools.site';

  test('health check', async ({ request }) => {
    const response = await request.get(`${baseURL}/health`);
    expect(response.status()).toBe(200);
  });

  test('should return CORS headers', async ({ request }) => {
    const response = await request.get(`${baseURL}/health`, {
      headers: {
        Origin: 'https://version-check.dev.devtools.site',
      },
    });

    expect(response.headers()['access-control-allow-origin']).toContain('version-check.dev.devtools.site');
  });
});
