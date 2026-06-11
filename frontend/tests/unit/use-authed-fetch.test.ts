import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useAuth } from '../../app/composables/useAuth'
import { consumeAuthErrorMessage, isAuthExpiredError, useAuthedFetch } from '../../app/composables/useAuthedFetch'

const API_BASE = process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1'

const storage = new Map<string, string>()
const sessionStore = new Map<string, string>()

const storageMock = (store: Map<string, string>) => ({
  getItem(key: string) {
    return store.has(key) ? store.get(key)! : null
  },
  setItem(key: string, value: string) {
    store.set(key, value)
  },
  removeItem(key: string) {
    store.delete(key)
  },
  clear() {
    store.clear()
  },
})

Object.defineProperty(globalThis, 'localStorage', {
  value: storageMock(storage),
  configurable: true,
})

Object.defineProperty(globalThis, 'sessionStorage', {
  value: storageMock(sessionStore),
  configurable: true,
})

const fetchMock = vi.fn()
vi.stubGlobal('$fetch', fetchMock)

const Harness = defineComponent({
  setup() {
    return { ...useAuth(), ...useAuthedFetch() }
  },
  template: '<div />',
})

const mountHarness = () => mountSuspended(Harness)

describe('useAuthedFetch', () => {
  beforeEach(async () => {
    storage.clear()
    sessionStore.clear()
    fetchMock.mockReset()
    const wrapper = await mountHarness()
    wrapper.vm.clearAuth()
    wrapper.vm.consumeAuthError()
    wrapper.unmount()
  })

  it('attaches the Authorization header when a token is present', async () => {
    fetchMock.mockResolvedValue({ ok: true })
    const wrapper = await mountHarness()
    wrapper.vm.setAuth('token-1', 'alice')

    const result = await wrapper.vm.authedFetch('/usage/current-month')

    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/usage/current-month`,
      { headers: { Authorization: 'Bearer token-1' } }
    )
  })

  it('sends no Authorization header without a token', async () => {
    fetchMock.mockResolvedValue({ ok: true })
    const wrapper = await mountHarness()

    await wrapper.vm.authedFetch('/usage/current-month')

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/usage/current-month`,
      { headers: {} }
    )
  })

  it('preserves caller-provided options and headers', async () => {
    fetchMock.mockResolvedValue({ ok: true })
    const wrapper = await mountHarness()
    wrapper.vm.setAuth('token-1', 'alice')

    await wrapper.vm.authedFetch('/scan/orgs/acme', {
      method: 'POST',
      headers: { 'X-Custom': 'yes' },
    })

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/scan/orgs/acme`,
      {
        method: 'POST',
        headers: { 'X-Custom': 'yes', Authorization: 'Bearer token-1' },
      }
    )
  })

  it.each([
    ['status', { status: 401 }],
    ['statusCode', { statusCode: 401 }],
    ['response.status', { response: { status: 401 } }],
    ['data.status', { data: { status: 401 } }],
    ['data.statusCode', { data: { statusCode: 401 } }],
  ])('clears auth and throws an auth-expired error on 401 via %s', async (_label, errorShape) => {
    fetchMock.mockRejectedValue(errorShape)
    const wrapper = await mountHarness()
    wrapper.vm.setAuth('token-1', 'alice')

    let caught: unknown
    try {
      await wrapper.vm.authedFetch('/usage/current-month')
    } catch (error) {
      caught = error
    }

    expect(isAuthExpiredError(caught)).toBe(true)
    expect((caught as { statusCode: number }).statusCode).toBe(401)
    expect(wrapper.vm.token).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(wrapper.vm.authError).toBe('Your GitHub authorization expired. Please sign in again.')
    expect(sessionStorage.getItem('auth_error_message')).toBe(
      'Your GitHub authorization expired. Please sign in again.'
    )
  })

  it('rethrows non-401 errors unchanged and keeps auth state', async () => {
    const original = Object.assign(new Error('boom'), { statusCode: 500 })
    fetchMock.mockRejectedValue(original)
    const wrapper = await mountHarness()
    wrapper.vm.setAuth('token-1', 'alice')

    await expect(wrapper.vm.authedFetch('/usage/current-month')).rejects.toBe(original)
    expect(wrapper.vm.token).toBe('token-1')
    expect(sessionStorage.getItem('auth_error_message')).toBeNull()
  })

  it('consumeAuthErrorMessage returns the stored message once', async () => {
    sessionStorage.setItem('auth_error_message', 'relogin please')

    expect(consumeAuthErrorMessage()).toBe('relogin please')
    expect(consumeAuthErrorMessage()).toBe('')
  })
})
