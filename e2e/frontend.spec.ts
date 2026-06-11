import { test, expect } from '@playwright/test';

test.describe('Version Checker Frontend', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should load the homepage', async ({ page }) => {
    await expect(page).toHaveTitle(/Version Checker/i);
  });

  test('should display main navigation with branding', async ({ page }) => {
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.locator('nav')).toContainText('Version Checker');
  });

  test('should show the dashboard heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('should offer GitHub login to an anonymous visitor', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Login/i })).toBeVisible();
  });

  test('auth callback without code shows a recoverable error', async ({ page }) => {
    await page.goto('/auth/callback');

    await expect(page.getByText(/Authentication Failed|認証に失敗しました/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Back to Dashboard|ダッシュボードに戻る/ })).toBeVisible();
  });
});
