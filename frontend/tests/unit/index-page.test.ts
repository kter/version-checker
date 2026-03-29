import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import IndexPage from '../../app/pages/index.vue'
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

const fetchMock = vi.fn()
vi.stubGlobal('$fetch', fetchMock)

const IndexHarness = defineComponent({
  components: { IndexPage },
  setup() {
    const auth = useAuth()
    auth.setAuth('token-1', 'octocat', [{ id: 1, login: 'octocat' }])
    return auth
  },
  template: '<IndexPage />',
})

describe('Index page', () => {
  beforeEach(() => {
    vi.useRealTimers()
    localStorageMock.clear()
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({ repository_count: 1, statuses: [], latest_job: null })
  })

  it('loads data for the first available account and enables scanning', async () => {
    const wrapper = await mountSuspended(IndexHarness)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/scan/orgs/octocat',
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(wrapper.text()).toContain('1 repositories found')
    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))
    expect(scanButton?.attributes('disabled')).toBeUndefined()
  })

  it('starts a scan job and polls until completion', async () => {
    vi.useFakeTimers()
    let refreshCount = 0
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url === '/_nuxt/builds/meta/test.json') {
        return Promise.resolve({})
      }
      if (url === 'http://localhost:8000/api/v1/scan/orgs/octocat' && options?.method === 'POST') {
        return Promise.resolve({
          job_id: 'job-1',
          org_id: 'octocat',
          status: 'queued',
          total_repos: 2,
          completed_repos: 0,
          failed_repos: 0,
          started_at: null,
          finished_at: null,
          error_message: null,
          created_at: '2026-03-28T12:00:00',
          updated_at: '2026-03-28T12:00:00'
        })
      }
      if (url === 'http://localhost:8000/api/v1/scan/orgs/octocat/jobs/job-1') {
        return Promise.resolve({
          job_id: 'job-1',
          org_id: 'octocat',
          status: 'completed',
          total_repos: 2,
          completed_repos: 2,
          failed_repos: 0,
          started_at: '2026-03-28T12:00:01',
          finished_at: '2026-03-28T12:00:10',
          error_message: null,
          created_at: '2026-03-28T12:00:00',
          updated_at: '2026-03-28T12:00:10'
        })
      }
      if (url === 'http://localhost:8000/api/v1/scan/orgs/octocat') {
        refreshCount += 1
        return Promise.resolve({
          repository_count: 1,
          statuses: refreshCount > 1 ? [
            {
              repo_id: 'octocat/app',
              framework: 'Nuxt',
              version: '3.16.0',
              is_eol: false,
              eol_date: null,
              last_scanned_at: '2026-03-28T12:00:10',
              source_path: 'package.json'
            }
          ] : [],
          latest_job: refreshCount > 1 ? {
            job_id: 'job-1',
            org_id: 'octocat',
            status: 'completed',
            total_repos: 2,
            completed_repos: 2,
            failed_repos: 0,
            started_at: '2026-03-28T12:00:01',
            finished_at: '2026-03-28T12:00:10',
            error_message: null,
            created_at: '2026-03-28T12:00:00',
            updated_at: '2026-03-28T12:00:10'
          } : null
        })
      }

      return Promise.resolve({})
    })

    const wrapper = await mountSuspended(IndexHarness)
    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))

    await scanButton!.trigger('click')
    await vi.runAllTicks()

    expect(fetchMock.mock.calls).toContainEqual([
      'http://localhost:8000/api/v1/scan/orgs/octocat',
      {
        method: 'POST',
        headers: { Authorization: 'Bearer token-1' }
      }
    ])

    await vi.advanceTimersByTimeAsync(3000)

    expect(fetchMock.mock.calls).toContainEqual([
      'http://localhost:8000/api/v1/scan/orgs/octocat/jobs/job-1',
      { headers: { Authorization: 'Bearer token-1' } }
    ])
    expect(fetchMock.mock.calls.filter(([url]) => url === 'http://localhost:8000/api/v1/scan/orgs/octocat').length).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('Nuxt')
  })
})
