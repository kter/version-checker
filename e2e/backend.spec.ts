import { test, expect } from '@playwright/test';

// Read-only smoke tests: no scans are triggered, so no paid AI usage occurs.
test.describe('Version Checker Backend API', () => {
  const baseURL = process.env.E2E_API_BASE_URL || 'https://api.version-check.dev.devtools.site';

  test('health check', async ({ request }) => {
    const response = await request.get(`${baseURL}/health`);
    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok' });
  });

  test('should return CORS headers', async ({ request }) => {
    const response = await request.get(`${baseURL}/health`, {
      headers: {
        Origin: 'https://version-check.dev.devtools.site',
      },
    });

    expect(response.headers()['access-control-allow-origin']).toContain('version-check.dev.devtools.site');
  });

  test('usage endpoint rejects unauthenticated requests', async ({ request }) => {
    const response = await request.get(`${baseURL}/api/v1/usage/current-month`);
    expect(response.status()).toBe(401);
  });

  test('scan results endpoint rejects unauthenticated requests', async ({ request }) => {
    const response = await request.get(`${baseURL}/api/v1/scan/orgs/some-org`);
    expect(response.status()).toBe(401);
  });

  test('scan endpoints reject forged bearer tokens', async ({ request }) => {
    const response = await request.get(`${baseURL}/api/v1/scan/orgs/some-org`, {
      headers: { Authorization: 'Bearer forged-token' },
    });
    expect(response.status()).toBe(401);
  });

  test('login endpoint redirects to GitHub OAuth', async ({ request }) => {
    const response = await request.get(`${baseURL}/api/v1/auth/login`, {
      maxRedirects: 0,
    });
    expect(response.status()).toBe(307);
    expect(response.headers()['location']).toContain('github.com/login/oauth/authorize');
  });
});
