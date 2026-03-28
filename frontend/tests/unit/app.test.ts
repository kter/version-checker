import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import App from '../../app/app.vue'
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

const AppHarness = defineComponent({
  components: { App },
  setup() {
    return useAuth()
  },
  template: '<App />',
})

describe('App', () => {
  beforeEach(() => {
    localStorageMock.clear()
  })

  it('shows the login button when no auth state is stored', async () => {
    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('Login with GitHub')
  })

  it('hydrates auth state from storage on mount', async () => {
    localStorage.setItem('auth_token', 'token-1')
    localStorage.setItem('auth_user', 'alice')
    localStorage.setItem('auth_orgs', JSON.stringify([{ id: 1, login: 'acme' }]))

    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).not.toContain('Login with GitHub')
  })

  it('reacts to auth state changes after the app is mounted', async () => {
    const wrapper = await mountSuspended(AppHarness)

    expect(wrapper.text()).toContain('Login with GitHub')

    wrapper.vm.setAuth('token-2', 'octocat', [{ id: 2, login: 'github' }])
    await nextTick()

    expect(wrapper.text()).toContain('octocat')
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
})
