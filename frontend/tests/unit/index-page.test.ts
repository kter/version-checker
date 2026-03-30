import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import IndexPage from '../../app/pages/index.vue'
import { useAuth } from '../../app/composables/useAuth'

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

const IndexHarness = defineComponent({
  components: { IndexPage },
  setup() {
    const auth = useAuth()
    auth.setAuth('token-1', 'octocat', [{ id: 1, login: 'octocat' }])
    return auth
  },
  template: '<IndexPage />',
})

const baseRepository = {
  repository_id: 'repo-1',
  repo_id: 'octocat/app',
  is_selected: true,
  framework: null,
  version: null,
  is_eol: null,
  eol_date: null,
  last_scanned_at: null,
  source_path: null,
}

describe('Index page', () => {
  beforeEach(() => {
    vi.useRealTimers()
    localStorageMock.clear()
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({
      repository_count: 1,
      selected_repository_count: 1,
      repositories: [baseRepository],
      latest_job: null,
    })
  })

  it('loads repositories for the first available account and enables scanning when selection is saved', async () => {
    const wrapper = await mountSuspended(IndexHarness)

    expect(fetchMock).toHaveBeenCalledWith(
      apiUrl('/scan/orgs/octocat'),
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(wrapper.text()).toContain('1 repositories found')
    expect(wrapper.text()).toContain('1 selected')
    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))
    expect(scanButton?.attributes('disabled')).toBeUndefined()
  })

  it('saves repository selection changes before scanning', async () => {
    let selectionSaved = false
    fetchMock.mockImplementation((url: string, options?: { method?: string, body?: { selected_repo_ids?: string[] } }) => {
      if (url === '/_nuxt/builds/meta/test.json') {
        return Promise.resolve({})
      }
      if (url === apiUrl('/scan/orgs/octocat/selection') && options?.method === 'PUT') {
        selectionSaved = true
        return Promise.resolve({ selected_repository_count: 0 })
      }
      if (url === apiUrl('/scan/orgs/octocat')) {
        return Promise.resolve({
          repository_count: 1,
          selected_repository_count: selectionSaved ? 0 : 1,
          repositories: [{
            ...baseRepository,
            is_selected: !selectionSaved
          }],
          latest_job: null,
        })
      }

      return Promise.resolve({})
    })

    const wrapper = await mountSuspended(IndexHarness)
    const checkbox = wrapper.find('input[type="checkbox"]')

    await checkbox.setValue(false)
    await wrapper.vm.$nextTick()

    const saveButton = wrapper.findAll('button').find(button => button.text().includes('Save Selection'))
    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))
    expect(wrapper.text()).toContain('Selection changes not saved')
    expect(scanButton?.attributes('disabled')).toBeDefined()

    await saveButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(fetchMock.mock.calls).toContainEqual([
      apiUrl('/scan/orgs/octocat/selection'),
      {
        method: 'PUT',
        body: { selected_repo_ids: [] },
        headers: { Authorization: 'Bearer token-1' }
      }
    ])
  })

  it('selects all repositories with one action', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 2,
      selected_repository_count: 1,
      repositories: [
        baseRepository,
        {
          ...baseRepository,
          repository_id: 'repo-2',
          repo_id: 'octocat/api',
          is_selected: false,
        }
      ],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)
    const selectAllButton = wrapper.findAll('button').find(button => button.text().includes('Select All'))

    await selectAllButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('2 selected')
    expect(wrapper.text()).toContain('Selection changes not saved')
    expect(wrapper.findAll('input[type="checkbox"]').every(input => input.element.checked)).toBe(true)
  })

  it('clears all repositories with one action', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 2,
      selected_repository_count: 2,
      repositories: [
        baseRepository,
        {
          ...baseRepository,
          repository_id: 'repo-2',
          repo_id: 'octocat/api',
        }
      ],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)
    const clearAllButton = wrapper.findAll('button').find(button => button.text().includes('Clear All'))

    await clearAllButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('0 selected')
    expect(wrapper.text()).toContain('Selection changes not saved')
    expect(wrapper.findAll('input[type="checkbox"]').every(input => !input.element.checked)).toBe(true)
  })

  it('starts a scan job and polls until completion', async () => {
    vi.useFakeTimers()
    let refreshCount = 0
    fetchMock.mockImplementation((url: string, options?: { method?: string }) => {
      if (url === '/_nuxt/builds/meta/test.json') {
        return Promise.resolve({})
      }
      if (url === apiUrl('/scan/orgs/octocat') && options?.method === 'POST') {
        return Promise.resolve({
          job_id: 'job-1',
          org_id: 'octocat',
          status: 'queued',
          total_repos: 1,
          completed_repos: 0,
          failed_repos: 0,
          started_at: null,
          finished_at: null,
          error_message: null,
          created_at: '2026-03-28T12:00:00',
          updated_at: '2026-03-28T12:00:00'
        })
      }
      if (url === apiUrl('/scan/orgs/octocat/jobs/job-1')) {
        return Promise.resolve({
          job_id: 'job-1',
          org_id: 'octocat',
          status: 'completed',
          total_repos: 1,
          completed_repos: 1,
          failed_repos: 0,
          started_at: '2026-03-28T12:00:01',
          finished_at: '2026-03-28T12:00:10',
          error_message: null,
          created_at: '2026-03-28T12:00:00',
          updated_at: '2026-03-28T12:00:10'
        })
      }
      if (url === apiUrl('/scan/orgs/octocat')) {
        refreshCount += 1
        return Promise.resolve({
          repository_count: 1,
          selected_repository_count: 1,
          repositories: refreshCount > 1 ? [
            {
              ...baseRepository,
              framework: 'Nuxt',
              version: '3.16.0',
              is_eol: false,
              last_scanned_at: '2026-03-28T12:00:10',
              source_path: 'package.json'
            }
          ] : [baseRepository],
          latest_job: refreshCount > 1 ? {
            job_id: 'job-1',
            org_id: 'octocat',
            status: 'completed',
            total_repos: 1,
            completed_repos: 1,
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
      apiUrl('/scan/orgs/octocat'),
      {
        method: 'POST',
        headers: { Authorization: 'Bearer token-1' }
      }
    ])

    await vi.advanceTimersByTimeAsync(3000)

    expect(fetchMock.mock.calls).toContainEqual([
      apiUrl('/scan/orgs/octocat/jobs/job-1'),
      { headers: { Authorization: 'Bearer token-1' } }
    ])
    expect(fetchMock.mock.calls.filter(([url]) => url === apiUrl('/scan/orgs/octocat')).length).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('Nuxt')
  })

  it('disables scanning when no repositories are selected', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 1,
      selected_repository_count: 0,
      repositories: [{
        ...baseRepository,
        is_selected: false
      }],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)
    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))

    expect(scanButton?.attributes('disabled')).toBeDefined()
  })
})
