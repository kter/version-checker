import { test, expect } from '@playwright/test';

test('has title and branding', async ({ page }) => {
    // Try to load the frontend from the dev server URL
    // We assume the frontend runs on port 3000
    await page.goto('http://localhost:3000/');

    // Expect a title "to contain" a substring.
    await expect(page).toHaveTitle(/Version Checker/i);

    // Expect the branding to be visible
    await expect(page.locator('text=Version Checker').first()).toBeVisible();
});

test('shows dashboard text', async ({ page }) => {
    await page.goto('http://localhost:3000/');

    // Dashboard text (from i18n or default)
    await expect(page.locator('text=Dashboard').first()).toBeVisible();
});
