import { test, expect } from '@playwright/test'

test('Language switching mechanism', async ({ page }) => {
    // Go to root
    await page.goto('/')

    // Initially it should be English (en is default)
    await expect(page.locator('button', { hasText: 'Login' })).toBeVisible()

    // Set cookie for Japanese locale and reload
    await page.context().addCookies([{ name: 'i18n_redirected', value: 'ja', domain: 'localhost', path: '/' }])
    await page.reload()

    // Verify that the button text changed to 'ログイン' (from ja.json)
    await expect(page.locator('button', { hasText: 'ログイン' })).toBeVisible()
})
