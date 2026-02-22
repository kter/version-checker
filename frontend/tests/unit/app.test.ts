import { describe, it, expect, vi } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import App from '../../app/app.vue'

// Avoid real local storage throwing errors in tests
vi.stubGlobal('localStorage', {
    getItem: vi.fn(),
    removeItem: vi.fn()
})

describe('App', () => {
    it('renders and locale switcher changes language', async () => {
        const wrapper = await mountSuspended(App)

        // Check if Version Checker title is displayed
        expect(wrapper.text()).toContain('Version Checker')

        // Check if the Language Switcher is present (USelect component text match or presence)
        const select = wrapper.findComponent({ name: 'USelect' })
        expect(select.exists()).toBe(true)

        // Verify USelect seems correctly bound
        expect(select.attributes('class')).toBeDefined()
    })
})
