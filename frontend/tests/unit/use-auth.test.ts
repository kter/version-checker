import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useAuth } from '../../app/composables/useAuth'

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

const AuthHarness = defineComponent({
  setup() {
    return { ...useAuth() }
  },
  template: '<div />',
})

const mountAuth = () => mountSuspended(AuthHarness)

describe('useAuth', () => {
  beforeEach(async () => {
    localStorageMock.clear()
    const wrapper = await mountAuth()
    wrapper.vm.clearAuth()
    wrapper.vm.consumeAuthError()
    wrapper.unmount()
  })

  it('persists auth state to localStorage on setAuth', async () => {
    const wrapper = await mountAuth()

    wrapper.vm.setAuth('token-1', 'alice', [{ id: 1, login: 'acme' }])

    expect(localStorage.getItem('auth_token')).toBe('token-1')
    expect(localStorage.getItem('auth_user')).toBe('alice')
    expect(localStorage.getItem('auth_orgs')).toBe(JSON.stringify([{ id: 1, login: 'acme' }]))
    expect(wrapper.vm.isAuthenticated).toBe(true)
  })

  it('defaults organizations to an empty list when omitted', async () => {
    const wrapper = await mountAuth()

    wrapper.vm.setAuth('token-1', 'alice')

    expect(wrapper.vm.organizations).toEqual([])
    expect(localStorage.getItem('auth_orgs')).toBe('[]')
  })

  it('hydrates state from localStorage via syncFromStorage', async () => {
    localStorage.setItem('auth_token', 'token-2')
    localStorage.setItem('auth_user', 'bob')
    localStorage.setItem('auth_orgs', JSON.stringify([{ id: 2, login: 'github' }]))

    const wrapper = await mountAuth()
    wrapper.vm.syncFromStorage()

    expect(wrapper.vm.token).toBe('token-2')
    expect(wrapper.vm.username).toBe('bob')
    expect(wrapper.vm.organizations).toEqual([{ id: 2, login: 'github' }])
  })

  it('falls back to an empty organization list when stored JSON is malformed', async () => {
    localStorage.setItem('auth_token', 'token-2')
    localStorage.setItem('auth_user', 'bob')
    localStorage.setItem('auth_orgs', '{not-json')

    const wrapper = await mountAuth()
    wrapper.vm.syncFromStorage()

    expect(wrapper.vm.organizations).toEqual([])
  })

  it('falls back to an empty organization list when stored JSON is not an array', async () => {
    localStorage.setItem('auth_orgs', JSON.stringify({ id: 1, login: 'acme' }))

    const wrapper = await mountAuth()
    wrapper.vm.syncFromStorage()

    expect(wrapper.vm.organizations).toEqual([])
  })

  it('clears state and storage via clearAuth', async () => {
    const wrapper = await mountAuth()
    wrapper.vm.setAuth('token-1', 'alice', [{ id: 1, login: 'acme' }])

    wrapper.vm.clearAuth()

    expect(wrapper.vm.token).toBeNull()
    expect(wrapper.vm.username).toBe('')
    expect(wrapper.vm.organizations).toEqual([])
    expect(wrapper.vm.isAuthenticated).toBe(false)
    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_user')).toBeNull()
    expect(localStorage.getItem('auth_orgs')).toBeNull()
  })

  it('is not authenticated when only a token is present', async () => {
    const wrapper = await mountAuth()
    wrapper.vm.setAuth('token-1', '')

    expect(wrapper.vm.isAuthenticated).toBe(false)
  })

  it('consumeAuthError returns the message once and clears it', async () => {
    const wrapper = await mountAuth()
    wrapper.vm.setAuthError('session expired')

    expect(wrapper.vm.consumeAuthError()).toBe('session expired')
    expect(wrapper.vm.consumeAuthError()).toBe('')
  })
})
