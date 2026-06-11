import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useAuth } from '../../app/composables/useAuth'
import { useMonthlyTokenUsage } from '../../app/composables/useMonthlyTokenUsage'
import { useScanJob } from '../../app/composables/useScanJob'

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

const NOW = new Date('2026-06-11T12:00:00.000Z')

const minutesAgo = (minutes: number, extraMs = 0) =>
  new Date(NOW.getTime() - minutes * 60 * 1000 - extraMs).toISOString()

const baseJob = {
  job_id: 'job-1',
  org_id: 'acme',
  status: 'running',
  total_repos: 5,
  completed_repos: 1,
  failed_repos: 0,
}

const Harness = defineComponent({
  setup() {
    return { ...useAuth(), ...useMonthlyTokenUsage(), ...useScanJob() }
  },
  template: '<div />',
})

const mountHarness = async () => {
  const wrapper = await mountSuspended(Harness)
  wrapper.vm.setActiveOrganization('acme')
  return wrapper
}

describe('useScanJob.syncJobState', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    storage.clear()
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({ ...baseJob })
    const wrapper = await mountSuspended(Harness)
    wrapper.vm.resetState()
    wrapper.vm.clear()
    wrapper.unmount()
  })

  afterEach(async () => {
    const wrapper = await mountSuspended(Harness)
    wrapper.vm.resetState()
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('normalizes status casing and string counts', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      status: 'RUNNING',
      total_repos: '5',
      completed_repos: '2',
      failed_repos: 'oops',
      updated_at: minutesAgo(0),
    })

    expect(job?.status).toBe('running')
    expect(job?.total_repos).toBe(5)
    expect(job?.completed_repos).toBe(2)
    expect(job?.failed_repos).toBe(0)
    expect(wrapper.vm.isScanning).toBe(true)
  })

  it('keeps a queued job active just below the 5 minute staleness limit', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      status: 'queued',
      total_repos: 0,
      completed_repos: 0,
      updated_at: minutesAgo(5, -1000),
    })

    expect(job?.status).toBe('queued')
    expect(wrapper.vm.isScanJobActive).toBe(true)
    expect(wrapper.vm.scanJobStatusLabel).not.toBe('')
  })

  it('finalizes a queued job as failed at the 5 minute staleness limit', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      status: 'queued',
      total_repos: 0,
      completed_repos: 0,
      updated_at: minutesAgo(5),
    })

    expect(job?.status).toBe('failed')
    expect(wrapper.vm.isScanJobActive).toBe(false)
    expect(wrapper.vm.scanErrorMessage).toBe(
      'The scan stalled before repository progress started. Please run it again.'
    )
  })

  it('finalizes a bootstrapping running job at the 3 minute staleness limit', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      total_repos: 0,
      completed_repos: 0,
      updated_at: minutesAgo(3),
    })

    expect(job?.status).toBe('failed')
    expect(wrapper.vm.scanErrorMessage).toBe(
      'The scan stalled before repository progress started. Please run it again.'
    )
  })

  it('keeps a bootstrapping running job active just below the 3 minute limit', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      total_repos: 0,
      completed_repos: 0,
      updated_at: minutesAgo(3, -1000),
    })

    expect(job?.status).toBe('running')
    expect(wrapper.vm.isScanJobActive).toBe(true)
  })

  it('finalizes a running job with pending repositories at the 15 minute limit', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      updated_at: minutesAgo(15),
    })

    expect(job?.status).toBe('failed')
    expect(wrapper.vm.scanErrorMessage).toBe(
      'The scan stalled while processing repositories. Please run it again.'
    )
  })

  it('keeps a running job with progress active just below the 15 minute limit', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      updated_at: minutesAgo(15, -1000),
    })

    expect(job?.status).toBe('running')
    expect(wrapper.vm.isScanJobActive).toBe(true)
  })

  it('does not finalize a running job whose repositories are all accounted for', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      completed_repos: 3,
      failed_repos: 2,
      updated_at: minutesAgo(60),
    })

    expect(job?.status).toBe('running')
  })

  it('does not treat a job without any timestamps as stale', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      status: 'queued',
      total_repos: 0,
    })

    expect(job?.status).toBe('queued')
  })

  it('falls back to started_at and created_at when updated_at is missing', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      status: 'queued',
      total_repos: 0,
      started_at: minutesAgo(6),
      created_at: minutesAgo(7),
    })

    expect(job?.status).toBe('failed')
  })

  it('clears the error and reports terminal state for a completed job', async () => {
    const wrapper = await mountHarness()

    const job = wrapper.vm.syncJobState({
      ...baseJob,
      status: 'completed',
      completed_repos: 5,
      finished_at: minutesAgo(0),
    })

    expect(job?.status).toBe('completed')
    expect(wrapper.vm.isScanning).toBe(false)
    expect(wrapper.vm.scanJobStatusLabel).toBe('')
    expect(wrapper.vm.terminalScanJobStatuses.has('completed')).toBe(true)
  })

  it('updates the monthly usage snapshot from the job payload', async () => {
    const wrapper = await mountHarness()

    wrapper.vm.syncJobState({
      ...baseJob,
      status: 'completed',
      completed_repos: 5,
      current_month_total_tokens: '7890',
    })

    expect(wrapper.vm.totalTokens).toBe(7890)
  })

  it('maps stalled error markers to localized messages', async () => {
    const wrapper = await mountHarness()

    expect(
      wrapper.vm.getScanJobErrorMessage({
        ...baseJob,
        error_message: 'Scan job stalled before repository progress started.',
      })
    ).toBe('The scan stalled before repository progress started. Please run it again.')
    expect(
      wrapper.vm.getScanJobErrorMessage({
        ...baseJob,
        error_message: 'Scan job stalled while processing repositories.',
      })
    ).toBe('The scan stalled while processing repositories. Please run it again.')
    expect(
      wrapper.vm.getScanJobErrorMessage({ ...baseJob, error_message: 'custom failure' })
    ).toBe('custom failure')
    expect(wrapper.vm.getScanJobErrorMessage(null)).toBe('Failed to run repository scan.')
  })

  it('switching the active organization clears the tracked job', async () => {
    const wrapper = await mountHarness()
    wrapper.vm.syncJobState({ ...baseJob, updated_at: minutesAgo(0) })
    expect(wrapper.vm.activeJob).not.toBeNull()

    wrapper.vm.setActiveOrganization('other-org')

    expect(wrapper.vm.activeJob).toBeNull()
    expect(wrapper.vm.activeOrg).toBe('other-org')
  })
})
