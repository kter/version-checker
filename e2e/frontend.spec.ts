import { test, expect } from '@playwright/test';

test.describe('Version Checker Frontend', () => {
  test.beforeEach(async ({ page }) => {
    // Wait for page to load
    await page.goto('/');
  });

  test('should load the homepage', async ({ page }) => {
    await expect(page).toHaveTitle(/Version Checker/i);
  });

  test('should display main navigation', async ({ page }) => {
    await expect(page.locator('nav')).toBeVisible();
  });

  test('should have API base URL configured', async ({ page }) => {
    // Check if the page loaded correctly
    await expect(page).toHaveURL(/version-check\.dev\.devtools\.site/);
  });
});
