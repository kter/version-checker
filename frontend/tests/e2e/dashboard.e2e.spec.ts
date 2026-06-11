import { test, expect, type Page } from '@playwright/test'

// All backend traffic is stubbed with page.route so these tests run without a
// real API, GitHub OAuth, or paid scan executions.

const scanResults = {
    repository_count: 2,
    selected_repository_count: 1,
    repositories: [
        {
            repository_id: 'repo-1',
            repo_id: 'acme/web-app',
            repository_updated_at: '2026-06-01T00:00:00',
            is_selected: true,
            detected_item_count: 1,
            detected_items: [
                {
                    name: 'Nuxt',
                    version: '2.15.8',
                    is_eol: true,
                    eol_date: '2024-06-30',
                    last_scanned_at: '2026-06-10T12:00:00',
                    source_path: 'package.json',
                },
            ],
            framework: 'Nuxt',
            version: '2.15.8',
            is_eol: true,
            eol_date: '2024-06-30',
            last_scanned_at: '2026-06-10T12:00:00',
            source_path: 'package.json',
        },
        {
            repository_id: 'repo-2',
            repo_id: 'acme/api-server',
            repository_updated_at: '2026-06-02T00:00:00',
            is_selected: false,
            detected_item_count: 0,
            detected_items: [],
            framework: null,
            version: null,
            is_eol: null,
            eol_date: null,
            last_scanned_at: null,
            source_path: null,
        },
    ],
    latest_job: null,
}

const seedAuthState = async (page: Page) => {
    await page.addInitScript(() => {
        localStorage.setItem('auth_token', 'e2e-token')
        localStorage.setItem('auth_user', 'e2e-user')
        localStorage.setItem('auth_orgs', JSON.stringify([{ id: 1, login: 'acme' }]))
    })
}

const stubBackend = async (page: Page) => {
    await page.route('**/api/v1/usage/current-month', route => route.fulfill({
        json: { total_tokens: 1234 },
    }))
    await page.route('**/api/v1/scan/orgs/acme', route => route.fulfill({
        json: scanResults,
    }))
}

test.describe('dashboard with a stubbed backend', () => {
    test.beforeEach(async ({ page }) => {
        await seedAuthState(page)
        await stubBackend(page)
        await page.goto('/')
    })

    test('shows the signed-in user and monthly token usage in the header', async ({ page }) => {
        await expect(page.locator('nav')).toContainText('e2e-user')
        await expect(page.locator('nav')).toContainText('This month: 1,234 tokens')
        await expect(page.getByRole('button', { name: 'Login with GitHub' })).toHaveCount(0)
    })

    test('renders repositories returned by the scan results API', async ({ page }) => {
        await expect(page.locator('[data-testid="repository-name"]')).toHaveCount(2)
        await expect(page.locator('[data-testid="repository-card-repo-1"]')).toContainText('acme/web-app')
        await expect(page.locator('[data-testid="repository-card-repo-1"]')).toContainText('Nuxt')
        await expect(page.getByText('2 repositories found')).toBeVisible()
        await expect(page.getByText('1 selected')).toBeVisible()
    })

    test('filters repository cards with the search box', async ({ page }) => {
        await expect(page.locator('[data-testid="repository-name"]')).toHaveCount(2)

        await page.getByPlaceholder('Search by repository, framework, version, or path').fill('web-app')

        await expect(page.locator('[data-testid="repository-name"]')).toHaveCount(1)
        await expect(page.locator('[data-testid="repository-card-repo-1"]')).toBeVisible()
        await expect(page.getByText('1 shown')).toBeVisible()
    })

    test('logout clears the session and shows the login button again', async ({ page }) => {
        await expect(page.locator('nav')).toContainText('e2e-user')

        // The logout button is the only button in the bordered account section.
        await page.locator('nav .border-l button').click()

        await expect(page.getByRole('button', { name: 'Login with GitHub' })).toBeVisible()
        const token = await page.evaluate(() => localStorage.getItem('auth_token'))
        expect(token).toBeNull()
    })
})

test('shows the login button when no auth state is present', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('button', { name: 'Login with GitHub' })).toBeVisible()
})
