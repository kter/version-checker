import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import App from '../../app/app.vue'
import { useAuth } from '../../app/composables/useAuth'
import { useMonthlyTokenUsage } from '../../app/composables/useMonthlyTokenUsage'

const API_BASE = process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1'

const apiUrl = (path: string) => `${API_BASE}${path}`

const storage = new Map<string, string>()

const localStorageMock = {
  getItem(key: string) {
    return storage.has(key) ? storage.get(key)! : null
  },
  setItem(key: string, value: string) {
    storage.set(key, value)
  },
  removeItem(key: string) {
    storage.delete(key)
  },
  clear() {
    storage.clear()
  },
}

Object.defineProperty(globalThis, 'localStorage', {
  value: localStorageMock,
  configurable: true,
})

const fetchMock = vi.fn()
vi.stubGlobal('$fetch', fetchMock)

const AppHarness = defineComponent({
  components: { App },
  setup() {
    return useAuth()
  },
  template: '<App />',
})

const AppStateResetHarness = defineComponent({
  setup() {
    const auth = useAuth()
    const monthlyUsage = useMonthlyTokenUsage()

    auth.clearAuth()
    monthlyUsage.clear()

    return () => null
  },
})

describe('App', () => {
  beforeEach(async () => {
    localStorageMock.clear()
    fetchMock.mockReset()
    const wrapper = await mountSuspended(AppStateResetHarness)
    wrapper.unmount()
    fetchMock.mockResolvedValue({
      total_tokens: 3456,
    })
  })

  it('shows the login button when no auth state is stored', async () => {
    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('Login with GitHub')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('hydrates auth state from storage on mount and shows monthly token usage', async () => {
    localStorage.setItem('auth_token', 'token-1')
    localStorage.setItem('auth_user', 'alice')
    localStorage.setItem('auth_orgs', JSON.stringify([{ id: 1, login: 'acme' }]))

    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).not.toContain('Login with GitHub')
    expect(fetchMock).toHaveBeenCalledWith(
      apiUrl('/usage/current-month'),
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(wrapper.text()).toContain('This month: 3,456 tokens')
  })

  it('reacts to auth state changes after the app is mounted', async () => {
    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('Login with GitHub')

    wrapper.vm.setAuth('token-2', 'octocat', [{ id: 2, login: 'github' }])
    await nextTick()
    await Promise.resolve()

    expect(wrapper.text()).toContain('octocat')
    expect(fetchMock).toHaveBeenCalledWith(
      apiUrl('/usage/current-month'),
      { headers: { Authorization: 'Bearer token-2' } }
    )
    expect(localStorage.getItem('auth_orgs')).toBe(
      JSON.stringify([{ id: 2, login: 'github' }])
    )

    wrapper.vm.clearAuth()
    await nextTick()

    expect(wrapper.text()).toContain('Login with GitHub')
    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_user')).toBeNull()
    expect(localStorage.getItem('auth_orgs')).toBeNull()
  })

  it('falls back to a dash when the usage request fails', async () => {
    fetchMock.mockReset()
    fetchMock.mockRejectedValue(new Error('usage failed'))
    localStorage.setItem('auth_token', 'token-1')
    localStorage.setItem('auth_user', 'alice')
    localStorage.setItem('auth_orgs', JSON.stringify([{ id: 1, login: 'acme' }]))

    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('This month: -')
  })
})
