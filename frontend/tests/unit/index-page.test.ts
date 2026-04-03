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
  detected_item_count: 0,
  detected_items: [],
  framework: null,
  version: null,
  is_eol: null,
  eol_date: null,
  last_scanned_at: null,
  source_path: null,
}

const buildDetectedItem = (overrides: Record<string, unknown> = {}) => ({
  name: 'Nuxt',
  version: '3.16.0',
  is_eol: false,
  eol_date: null,
  last_scanned_at: '2026-03-28T12:00:10',
  source_path: 'frontend/package.json',
  ...overrides,
})

const getRenderedRepositoryNames = (wrapper: Awaited<ReturnType<typeof mountSuspended>>) => {
  return wrapper.findAll('[data-testid="repository-name"]').map(node => node.text())
}

const getMonitoringCheckboxes = (wrapper: Awaited<ReturnType<typeof mountSuspended>>) => {
  return wrapper.findAll('[data-testid^="repository-checkbox-"]')
}

describe('Index page', () => {
  beforeEach(() => {
    vi.useRealTimers()
    localStorageMock.clear()
    document.body.innerHTML = ''
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
    expect(wrapper.text()).toContain('1 shown')
    expect(wrapper.text()).toContain('1 selected')
    expect(wrapper.text()).toContain('This saves which repositories are monitored and included in scans.')
    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))
    expect(scanButton?.attributes('disabled')).toBeUndefined()
  })

  it('saves repository selection changes before scanning when scan is triggered with unsaved changes', async () => {
    let selectionSaved = false
    fetchMock.mockImplementation((url: string, options?: { method?: string, body?: { selected_repo_ids?: string[] } }) => {
      if (url === '/_nuxt/builds/meta/test.json') {
        return Promise.resolve({})
      }
      if (url === apiUrl('/scan/orgs/octocat/selection') && options?.method === 'PUT') {
        selectionSaved = true
        return Promise.resolve({ selected_repository_count: 0 })
      }
      if (url === apiUrl('/scan/orgs/octocat') && options?.method === 'POST') {
        return Promise.resolve({
          job_id: 'job-1',
          org_id: 'octocat',
          status: 'queued',
          total_repos: 0,
          completed_repos: 0,
          failed_repos: 0,
          started_at: null,
          finished_at: null,
          error_message: null,
          created_at: '2026-03-28T12:00:00',
          updated_at: '2026-03-28T12:00:00'
        })
      }
      if (url === apiUrl('/scan/orgs/octocat')) {
        return Promise.resolve({
          repository_count: 2,
          selected_repository_count: selectionSaved ? 1 : 2,
          repositories: [
            {
              ...baseRepository,
              repository_id: 'repo-1',
              repo_id: 'octocat/app',
              is_selected: false,
            },
            {
              ...baseRepository,
              repository_id: 'repo-2',
              repo_id: 'octocat/api',
              is_selected: true,
            }
          ],
          latest_job: null,
        })
      }

      return Promise.resolve({})
    })

    const wrapper = await mountSuspended(IndexHarness)
    const checkbox = wrapper.find('[data-testid="repository-checkbox-repo-1"]')

    await checkbox.setValue(true)
    await wrapper.vm.$nextTick()

    const scanButton = wrapper.findAll('button').find(button => button.text().includes('Scan Repositories'))
    expect(wrapper.text()).toContain('Selection changes not saved')
    expect(scanButton?.attributes('disabled')).toBeUndefined()

    await scanButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(fetchMock.mock.calls).toContainEqual([
      apiUrl('/scan/orgs/octocat/selection'),
      {
        method: 'PUT',
        body: { selected_repo_ids: ['repo-1', 'repo-2'] },
        headers: { Authorization: 'Bearer token-1' }
      }
    ])
    expect(fetchMock.mock.calls).toContainEqual([
      apiUrl('/scan/orgs/octocat'),
      {
        method: 'POST',
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
    expect(getMonitoringCheckboxes(wrapper).every(input => input.element.checked)).toBe(true)
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
    expect(getMonitoringCheckboxes(wrapper).every(input => !input.element.checked)).toBe(true)
  })

  it('disables monitoring for marked repositories in one action', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 3,
      selected_repository_count: 3,
      repositories: [
        {
          ...baseRepository,
          repository_id: 'repo-1',
          repo_id: 'octocat/app',
        },
        {
          ...baseRepository,
          repository_id: 'repo-2',
          repo_id: 'octocat/api',
        },
        {
          ...baseRepository,
          repository_id: 'repo-3',
          repo_id: 'octocat/docs',
        }
      ],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)

    await wrapper.find('[data-testid="bulk-selection-checkbox-repo-1"]').setValue(true)
    await wrapper.find('[data-testid="bulk-selection-checkbox-repo-3"]').setValue(true)
    await wrapper.vm.$nextTick()

    const disableMonitoringButton = wrapper.findAll('button').find(button => button.text().includes('Disable Monitoring'))
    await disableMonitoringButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('1 selected')
    expect(wrapper.text()).toContain('Selection changes not saved')
    expect(wrapper.find('[data-testid="repository-checkbox-repo-1"]').element.checked).toBe(false)
    expect(wrapper.find('[data-testid="repository-checkbox-repo-2"]').element.checked).toBe(true)
    expect(wrapper.find('[data-testid="repository-checkbox-repo-3"]').element.checked).toBe(false)
  })

  it('filters repositories by search query', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 3,
      selected_repository_count: 2,
      repositories: [
        baseRepository,
        {
          ...baseRepository,
          repository_id: 'repo-2',
          repo_id: 'octocat/api',
          framework: 'Node.js',
          version: '20.11.0',
          source_path: 'frontend/package.json',
          detected_item_count: 2,
          detected_items: [
            buildDetectedItem({
              name: 'Node.js',
              version: '20.11.0',
              source_path: 'frontend/package.json',
            }),
            buildDetectedItem({
              name: 'FastAPI',
              version: '0.110.0',
              source_path: 'backend/pyproject.toml',
            })
          ]
        },
        {
          ...baseRepository,
          repository_id: 'repo-3',
          repo_id: 'octocat/docs',
          is_selected: false,
          framework: 'Nuxt',
          version: '3.16.0',
          source_path: 'frontend/package.json',
        }
      ],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)
    const searchInput = wrapper.find('input[type="search"]')

    await searchInput.setValue('fastapi')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('1 shown')
    expect(wrapper.text()).toContain('octocat/api')
    expect(wrapper.text()).not.toContain('octocat/app')
    expect(wrapper.text()).not.toContain('octocat/docs')
  })

  it('opens repository details modal with all detected items from the card', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 1,
      selected_repository_count: 1,
      repositories: [{
        ...baseRepository,
        framework: 'Node.js',
        version: '18.0.0',
        is_eol: true,
        eol_date: '2025-04-30T00:00:00',
        last_scanned_at: '2026-03-28T12:00:00',
        source_path: 'frontend/package.json',
        detected_item_count: 3,
        detected_items: [
          buildDetectedItem({
            name: 'Node.js',
            version: '18.0.0',
            is_eol: true,
            eol_date: '2025-04-30T00:00:00',
            last_scanned_at: '2026-03-28T12:00:00',
            source_path: 'frontend/package.json',
          }),
          buildDetectedItem({
            name: 'Nuxt',
            version: '3.16.0',
            last_scanned_at: '2026-03-29T12:00:00',
            source_path: 'frontend/package.json',
          }),
          buildDetectedItem({
            name: 'FastAPI',
            version: '0.110.0',
            last_scanned_at: '2026-03-27T12:00:00',
            source_path: 'backend/pyproject.toml',
          })
        ]
      }],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)

    await wrapper.find('[data-testid="repository-card-repo-1"]').trigger('click')
    await wrapper.vm.$nextTick()

    const pageText = document.body.textContent || ''
    expect(pageText).toContain('octocat/app')
    expect(pageText).toContain('3 detected items')
    expect(pageText).toContain('Node.js')
    expect(pageText).toContain('Nuxt')
    expect(pageText).toContain('FastAPI')
  })

  it('does not open repository details modal when toggling repository checkboxes', async () => {
    const wrapper = await mountSuspended(IndexHarness)

    await wrapper.find('[data-testid="repository-checkbox-repo-1"]').setValue(false)
    await wrapper.vm.$nextTick()

    expect(document.body.querySelector('[data-testid="repository-details-modal"]')).toBeNull()
  })

  it('filters repositories by monitoring and scan status', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 3,
      selected_repository_count: 2,
      repositories: [
        {
          ...baseRepository,
          repository_id: 'repo-1',
          repo_id: 'octocat/web',
          framework: 'Nuxt',
          version: '3.16.0',
          is_eol: false,
        },
        {
          ...baseRepository,
          repository_id: 'repo-2',
          repo_id: 'octocat/legacy',
          is_selected: false,
          framework: 'Rails',
          version: '6.1',
          is_eol: true,
        },
        {
          ...baseRepository,
          repository_id: 'repo-3',
          repo_id: 'octocat/worker',
          framework: null,
          version: null,
          is_eol: null,
        }
      ],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)
    const [monitoringSelect, statusSelect] = wrapper.findAll('select')

    await monitoringSelect.setValue('disabled')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('1 shown')
    expect(wrapper.text()).toContain('octocat/legacy')
    expect(wrapper.text()).not.toContain('octocat/web')
    expect(wrapper.text()).not.toContain('octocat/worker')

    await statusSelect.setValue('pending')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('No matching repositories')

    const clearFiltersButton = wrapper.findAll('button').find(button => button.text().includes('Clear Filters'))
    await clearFiltersButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('3 shown')
    expect(wrapper.text()).toContain('octocat/web')
    expect(wrapper.text()).toContain('octocat/legacy')
    expect(wrapper.text()).toContain('octocat/worker')
  })

  it('sorts repositories using the selected sort option', async () => {
    fetchMock.mockResolvedValue({
      repository_count: 4,
      selected_repository_count: 3,
      repositories: [
        {
          ...baseRepository,
          repository_id: 'repo-1',
          repo_id: 'octocat/worker',
          framework: 'FastAPI',
          version: '0.110.0',
          is_eol: false,
          last_scanned_at: '2026-03-28T12:00:10',
        },
        {
          ...baseRepository,
          repository_id: 'repo-2',
          repo_id: 'octocat/app',
          framework: 'Rails',
          version: '6.1',
          is_eol: true,
          last_scanned_at: '2026-03-27T12:00:10',
        },
        {
          ...baseRepository,
          repository_id: 'repo-3',
          repo_id: 'octocat/docs',
          framework: null,
          version: null,
          is_eol: null,
          last_scanned_at: null,
        },
        {
          ...baseRepository,
          repository_id: 'repo-4',
          repo_id: 'octocat/api',
          framework: 'Nuxt',
          version: '3.16.0',
          is_eol: false,
          last_scanned_at: '2026-03-29T12:00:10',
        }
      ],
      latest_job: null,
    })

    const wrapper = await mountSuspended(IndexHarness)
    const sortSelect = wrapper.find('[data-testid="sort-select"]')

    expect(getRenderedRepositoryNames(wrapper)).toEqual([
      'octocat/api',
      'octocat/app',
      'octocat/docs',
      'octocat/worker'
    ])

    await sortSelect.setValue('repository_desc')
    await wrapper.vm.$nextTick()

    expect(getRenderedRepositoryNames(wrapper)).toEqual([
      'octocat/worker',
      'octocat/docs',
      'octocat/app',
      'octocat/api'
    ])

    await sortSelect.setValue('status_priority')
    await wrapper.vm.$nextTick()

    expect(getRenderedRepositoryNames(wrapper)).toEqual([
      'octocat/app',
      'octocat/docs',
      'octocat/api',
      'octocat/worker'
    ])

    await sortSelect.setValue('last_scanned_desc')
    await wrapper.vm.$nextTick()

    expect(getRenderedRepositoryNames(wrapper)).toEqual([
      'octocat/api',
      'octocat/worker',
      'octocat/app',
      'octocat/docs'
    ])
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

  it('clears auth when repository loading returns 401', async () => {
    fetchMock.mockRejectedValue({ statusCode: 401 })

    const wrapper = await mountSuspended(IndexHarness)
    await wrapper.vm.$nextTick()

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_user')).toBeNull()
    expect(localStorage.getItem('auth_orgs')).toBeNull()
  })
})
