import { test, expect } from '@playwright/test';

test.describe('Version Checker Backend API', () => {
  const baseURL = 'https://s5jrluvwfn66cxzr52nveb7hym0ajspj.lambda-url.ap-northeast-1.on.aws/api/v1';

  test('health check', async ({ request }) => {
    const response = await request.get(`${baseURL}/health`);
    expect(response.status()).toBe(200);
  });

  test('should return CORS headers', async ({ request }) => {
    const response = await request.get(`${baseURL}/`);
    expect(response.headers()['access-control-allow-origin']).toContain('version-check.dev.devtools.site');
  });
});
