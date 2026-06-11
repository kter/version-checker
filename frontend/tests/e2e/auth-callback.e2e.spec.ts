import { test, expect } from '@playwright/test'

// The OAuth code exchange is stubbed with page.route, so no real GitHub
// credentials are involved.

test.describe('auth callback page', () => {
    test('shows an error when no code is provided', async ({ page }) => {
        await page.goto('/auth/callback')

        await expect(page.getByText('Authentication Failed')).toBeVisible()
        await expect(page.getByText('No authentication code provided.')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Back to Dashboard' })).toBeVisible()
    })

    test('stores the session and redirects to the dashboard on success', async ({ page }) => {
        await page.route('**/api/v1/auth/callback?*', route => route.fulfill({
            json: {
                access_token: 'e2e-jwt',
                user: { username: 'e2e-user' },
                organizations: [{ id: 1, login: 'acme' }],
            },
        }))
        await page.route('**/api/v1/usage/current-month', route => route.fulfill({
            json: { total_tokens: 0 },
        }))
        await page.route('**/api/v1/scan/orgs/acme', route => route.fulfill({
            json: {
                repository_count: 0,
                selected_repository_count: 0,
                repositories: [],
                latest_job: null,
            },
        }))

        await page.goto('/auth/callback?code=e2e-code')

        await page.waitForURL('**/')
        await expect(page.locator('nav')).toContainText('e2e-user')
        const token = await page.evaluate(() => localStorage.getItem('auth_token'))
        expect(token).toBe('e2e-jwt')
    })

    test('surfaces the backend error detail when the exchange fails', async ({ page }) => {
        await page.route('**/api/v1/auth/callback?*', route => route.fulfill({
            status: 400,
            json: { detail: 'Bad verification code' },
        }))

        await page.goto('/auth/callback?code=bad-code')

        await expect(page.getByText('Authentication Failed')).toBeVisible()
        await expect(page.getByText('Bad verification code')).toBeVisible()
    })
})
