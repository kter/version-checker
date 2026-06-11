import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useAuth } from '../../app/composables/useAuth'
import { useMonthlyTokenUsage } from '../../app/composables/useMonthlyTokenUsage'

const storage = new Map<string, string>()

Object.defineProperty(globalThis, 'localStorage', {
  value: {
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
  },
  configurable: true,
})

const fetchMock = vi.fn()
vi.stubGlobal('$fetch', fetchMock)

const Harness = defineComponent({
  setup() {
    return { ...useAuth(), ...useMonthlyTokenUsage() }
  },
  template: '<div />',
})

const mountHarness = () => mountSuspended(Harness)

describe('useMonthlyTokenUsage', () => {
  beforeEach(async () => {
    storage.clear()
    fetchMock.mockReset()
    const wrapper = await mountHarness()
    wrapper.vm.clearAuth()
    wrapper.vm.clear()
    wrapper.unmount()
  })

  it('fetches the current month usage when a token is present', async () => {
    fetchMock.mockResolvedValue({ total_tokens: 1234 })
    const wrapper = await mountHarness()
    wrapper.vm.setAuth('token-1', 'alice')

    await wrapper.vm.fetchCurrentMonthUsage()

    expect(wrapper.vm.totalTokens).toBe(1234)
    expect(wrapper.vm.isReady).toBe(true)
    expect(wrapper.vm.isLoading).toBe(false)
  })

  it('clears state instead of fetching when no token is present', async () => {
    const wrapper = await mountHarness()

    await wrapper.vm.fetchCurrentMonthUsage()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(wrapper.vm.totalTokens).toBeNull()
    expect(wrapper.vm.isReady).toBe(false)
  })

  it('marks the state ready with a null total when the request fails', async () => {
    fetchMock.mockRejectedValue(new Error('boom'))
    const wrapper = await mountHarness()
    wrapper.vm.setAuth('token-1', 'alice')

    await wrapper.vm.fetchCurrentMonthUsage()

    expect(wrapper.vm.totalTokens).toBeNull()
    expect(wrapper.vm.isReady).toBe(true)
    expect(wrapper.vm.isLoading).toBe(false)
  })

  it.each([
    ['number', 42, 42],
    ['numeric string', '42', 42],
    ['zero', 0, 0],
  ])('syncCurrentMonthUsage accepts a %s snapshot', async (_label, input, expected) => {
    const wrapper = await mountHarness()

    wrapper.vm.syncCurrentMonthUsage(input)

    expect(wrapper.vm.totalTokens).toBe(expected)
    expect(wrapper.vm.isReady).toBe(true)
  })

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['non-numeric string', 'NaN-ish'],
  ])('syncCurrentMonthUsage ignores a %s snapshot', async (_label, input) => {
    const wrapper = await mountHarness()
    wrapper.vm.syncCurrentMonthUsage(100)

    wrapper.vm.syncCurrentMonthUsage(input)

    expect(wrapper.vm.totalTokens).toBe(100)
  })
})
