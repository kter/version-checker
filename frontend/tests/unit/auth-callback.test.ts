import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import AuthCallback from '../../app/pages/auth/callback.vue'

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

let routeQuery: Record<string, string | string[]> = {}
const routerPushMock = vi.fn()

mockNuxtImport('useRoute', () => () => ({ query: routeQuery }))
// Nuxt internals (payload plugin, test-utils entry) also call useRouter(),
// so the mock must expose the router hooks they register.
mockNuxtImport('useRouter', () => () => ({
  push: routerPushMock,
  replace: vi.fn(),
  beforeEach: vi.fn(),
  beforeResolve: vi.fn(),
  afterEach: vi.fn(),
  onError: vi.fn(),
  resolve: vi.fn(),
  currentRoute: { value: { path: '/auth/callback', query: routeQuery } },
}))

const mountCallback = async (query: Record<string, string | string[]>) => {
  routeQuery = query
  const wrapper = await mountSuspended(AuthCallback)
  await flushPromises()
  await nextTick()
  return wrapper
}

describe('auth callback page', () => {
  beforeEach(() => {
    storage.clear()
    sessionStore.clear()
    fetchMock.mockReset()
    routerPushMock.mockReset()
  })

  it('shows an error when no code is present in the query', async () => {
    const wrapper = await mountCallback({})

    expect(wrapper.text()).toContain('Authentication Failed')
    expect(wrapper.text()).toContain('No authentication code provided.')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(routerPushMock).not.toHaveBeenCalled()
  })

  it('rejects a code that was already exchanged in this session', async () => {
    sessionStorage.setItem('github_oauth_exchange:abc', 'done')

    const wrapper = await mountCallback({ code: 'abc' })

    expect(wrapper.text()).toContain(
      'This authentication response was already used. Please start login again.'
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('stores auth state and redirects to the dashboard on success', async () => {
    fetchMock.mockResolvedValue({
      access_token: 'jwt-token',
      user: { username: 'alice' },
      organizations: [{ id: 1, login: 'acme' }],
    })

    const wrapper = await mountCallback({ code: 'abc' })

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/auth/callback`,
      { query: { code: 'abc' } }
    )
    expect(sessionStorage.getItem('github_oauth_exchange:abc')).toBe('done')
    expect(localStorage.getItem('auth_token')).toBe('jwt-token')
    expect(localStorage.getItem('auth_user')).toBe('alice')
    expect(localStorage.getItem('auth_orgs')).toBe(JSON.stringify([{ id: 1, login: 'acme' }]))
    expect(routerPushMock).toHaveBeenCalledWith('/')
    expect(wrapper.text()).not.toContain('Authentication Failed')
  })

  it('uses the first code when the query parameter is repeated', async () => {
    fetchMock.mockResolvedValue({
      access_token: 'jwt-token',
      user: { username: 'alice' },
      organizations: [],
    })

    await mountCallback({ code: ['abc', 'def'] })

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/auth/callback`,
      { query: { code: 'abc' } }
    )
  })

  it('shows the backend message when the response has no access token', async () => {
    fetchMock.mockResolvedValue({ message: 'OAuth exchange rejected' })

    const wrapper = await mountCallback({ code: 'abc' })

    expect(wrapper.text()).toContain('Authentication Failed')
    expect(wrapper.text()).toContain('OAuth exchange rejected')
    expect(sessionStorage.getItem('github_oauth_exchange:abc')).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(routerPushMock).not.toHaveBeenCalled()
  })

  it('shows the API error detail when the exchange request fails', async () => {
    fetchMock.mockRejectedValue({ data: { detail: 'Bad verification code' } })

    const wrapper = await mountCallback({ code: 'abc' })

    expect(wrapper.text()).toContain('Authentication Failed')
    expect(wrapper.text()).toContain('Bad verification code')
    expect(sessionStorage.getItem('github_oauth_exchange:abc')).toBeNull()
    expect(routerPushMock).not.toHaveBeenCalled()
  })
})
