type ScanJob = {
  job_id: string
  org_id?: string | null
  status: string
  total_repos?: number | string | null
  completed_repos?: number | string | null
  failed_repos?: number | string | null
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
  created_at?: string | null
  updated_at?: string | null
  current_month_total_tokens?: number | string | null
}

const BOOTSTRAP_STALLED_SCAN_JOB_ERROR_MESSAGE = 'Scan job stalled before repository progress started.'
const PROGRESS_STALLED_SCAN_JOB_ERROR_MESSAGE = 'Scan job stalled while processing repositories.'
const SCAN_JOB_QUEUE_STALE_AFTER_MS = 5 * 60 * 1000
const SCAN_JOB_BOOTSTRAP_STALE_AFTER_MS = 3 * 60 * 1000
const SCAN_JOB_PROGRESS_STALE_AFTER_MS = 15 * 60 * 1000
const ACTIVE_SCAN_JOB_STATUSES = new Set(['queued', 'running'])
const TERMINAL_SCAN_JOB_STATUSES = new Set(['completed', 'partial_failed', 'failed'])

let pollingHandle: ReturnType<typeof setInterval> | null = null
let isPollingRequestInFlight = false

const normalizeJobCount = (value: number | string | null | undefined) => {
  const normalizedCount = Number(value)
  return Number.isFinite(normalizedCount) ? normalizedCount : 0
}

const parseSortableTimestamp = (value: string | null | undefined) => {
  if (!value) {
    return null
  }

  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

const normalizeJob = (job: ScanJob | null | undefined): ScanJob | null => {
  if (!job) {
    return null
  }

  return {
    ...job,
    status: String(job.status || '').toLowerCase(),
    total_repos: normalizeJobCount(job.total_repos),
    completed_repos: normalizeJobCount(job.completed_repos),
    failed_repos: normalizeJobCount(job.failed_repos),
  }
}

const getScanJobReferenceTimestamp = (job: ScanJob | null) => {
  return parseSortableTimestamp(job?.updated_at)
    ?? parseSortableTimestamp(job?.started_at)
    ?? parseSortableTimestamp(job?.created_at)
}

const isScanJobStale = (job: ScanJob | null) => {
  if (!job || !ACTIVE_SCAN_JOB_STATUSES.has(job.status)) {
    return false
  }

  const referenceTimestamp = getScanJobReferenceTimestamp(job)
  if (referenceTimestamp === null) {
    return false
  }

  const ageInMilliseconds = Date.now() - referenceTimestamp
  if (job.status === 'queued') {
    return ageInMilliseconds >= SCAN_JOB_QUEUE_STALE_AFTER_MS
  }
  if (job.status === 'running' && job.total_repos === 0) {
    return ageInMilliseconds >= SCAN_JOB_BOOTSTRAP_STALE_AFTER_MS
  }
  if (
    job.status === 'running'
    && normalizeJobCount(job.completed_repos) + normalizeJobCount(job.failed_repos) < normalizeJobCount(job.total_repos)
  ) {
    return ageInMilliseconds >= SCAN_JOB_PROGRESS_STALE_AFTER_MS
  }
  return false
}

const finalizeStaleJob = (job: ScanJob) => {
  const finalizedAt = new Date().toISOString()
  const stalledErrorMessage = job.status === 'queued' || job.total_repos === 0
    ? BOOTSTRAP_STALLED_SCAN_JOB_ERROR_MESSAGE
    : PROGRESS_STALLED_SCAN_JOB_ERROR_MESSAGE

  return {
    ...job,
    status: 'failed',
    error_message: job.error_message || stalledErrorMessage,
    finished_at: job.finished_at || finalizedAt,
    updated_at: finalizedAt,
  }
}

export const useScanJob = () => {
  const { authedFetch } = useAuthedFetch()
  const { fetchCurrentMonthUsage, syncCurrentMonthUsage } = useMonthlyTokenUsage()
  const { t } = useI18n()

  const activeOrg = useState<string>('scan.activeOrg', () => '')
  const activeJob = useState<ScanJob | null>('scan.activeJob', () => null)
  const pollingJobId = useState<string>('scan.pollingJobId', () => '')
  const scanErrorMessage = useState<string>('scan.errorMessage', () => '')

  const isScanJobActive = computed(() => {
    return Boolean(activeJob.value && ACTIVE_SCAN_JOB_STATUSES.has(activeJob.value.status))
  })

  const isScanning = computed(() => isScanJobActive.value)

  const scanJobStatusLabel = computed(() => {
    if (!activeJob.value || !isScanJobActive.value) {
      return ''
    }
    if (activeJob.value.status === 'queued') {
      return t('scan_queued')
    }
    return t('scan_running')
  })

  const scanJobDetailLabel = computed(() => {
    if (!activeJob.value || !isScanJobActive.value) {
      return ''
    }
    if (activeJob.value.status === 'queued' || activeJob.value.total_repos === 0) {
      return t('scan_preparing')
    }
    return t('scan_progress', {
      completed: activeJob.value.completed_repos,
      total: activeJob.value.total_repos
    })
  })

  const clearScanError = () => {
    scanErrorMessage.value = ''
  }

  const getScanJobErrorMessage = (job: ScanJob | null) => {
    if (job?.error_message === BOOTSTRAP_STALLED_SCAN_JOB_ERROR_MESSAGE) {
      return t('scan_stalled_message')
    }
    if (job?.error_message === PROGRESS_STALLED_SCAN_JOB_ERROR_MESSAGE) {
      return t('scan_progress_stalled_message')
    }
    return job?.error_message || t('scan_failed_message')
  }

  const stopPolling = () => {
    if (pollingHandle) {
      clearInterval(pollingHandle)
      pollingHandle = null
    }
    pollingJobId.value = ''
    isPollingRequestInFlight = false
  }

  const resetState = () => {
    stopPolling()
    activeOrg.value = ''
    activeJob.value = null
    clearScanError()
  }

  const setActiveOrganization = (organization: string) => {
    if (activeOrg.value === organization) {
      return
    }

    stopPolling()
    activeOrg.value = organization
    activeJob.value = null
    clearScanError()
  }

  const loadScanJob = async (jobId: string) => {
    return await authedFetch<ScanJob>(`/scan/orgs/${activeOrg.value}/jobs/${jobId}`)
  }

  const pollJobStatus = async (jobId: string) => {
    if (!import.meta.client || !activeOrg.value || pollingJobId.value !== jobId || isPollingRequestInFlight) {
      return
    }

    isPollingRequestInFlight = true

    try {
      const response = await loadScanJob(jobId)
      const effectiveJob = syncJobState(response)
      if (effectiveJob && TERMINAL_SCAN_JOB_STATUSES.has(effectiveJob.status)) {
        const terminalError = effectiveJob.status === 'partial_failed' || effectiveJob.status === 'failed'
          ? getScanJobErrorMessage(effectiveJob)
          : ''
        scanErrorMessage.value = terminalError
        await fetchCurrentMonthUsage()
      }
    } catch (error) {
      stopPolling()
      activeJob.value = null
      const candidate = error as { data?: { detail?: string }, message?: string }
      scanErrorMessage.value = candidate.data?.detail || candidate.message || t('scan_failed_message')
    } finally {
      isPollingRequestInFlight = false
    }
  }

  const startPolling = (jobId: string) => {
    if (!import.meta.client || !activeOrg.value) {
      return
    }

    if (pollingJobId.value && pollingJobId.value !== jobId) {
      stopPolling()
    }

    pollingJobId.value = jobId
    if (pollingHandle) {
      return
    }

    pollingHandle = setInterval(() => {
      if (!pollingJobId.value) {
        return
      }
      void pollJobStatus(pollingJobId.value)
    }, 3000)

    void pollJobStatus(jobId)
  }

  const syncJobState = (job: ScanJob | null | undefined) => {
    const normalizedJob = normalizeJob(job)
    const effectiveJob = isScanJobStale(normalizedJob)
      ? finalizeStaleJob(normalizedJob as ScanJob)
      : normalizedJob

    if (normalizedJob?.current_month_total_tokens !== undefined) {
      syncCurrentMonthUsage(normalizedJob.current_month_total_tokens)
    }

    activeJob.value = effectiveJob

    if (effectiveJob && ACTIVE_SCAN_JOB_STATUSES.has(effectiveJob.status)) {
      clearScanError()
      startPolling(effectiveJob.job_id)
      return effectiveJob
    }

    if (
      effectiveJob?.error_message === BOOTSTRAP_STALLED_SCAN_JOB_ERROR_MESSAGE
      || effectiveJob?.error_message === PROGRESS_STALLED_SCAN_JOB_ERROR_MESSAGE
    ) {
      scanErrorMessage.value = getScanJobErrorMessage(effectiveJob)
    }

    stopPolling()
    return effectiveJob
  }

  return {
    activeOrg,
    activeJob,
    scanErrorMessage,
    isScanning,
    isScanJobActive,
    scanJobStatusLabel,
    scanJobDetailLabel,
    setActiveOrganization,
    syncJobState,
    clearScanError,
    getScanJobErrorMessage,
    stopPolling,
    resetState,
    activeScanJobStatuses: ACTIVE_SCAN_JOB_STATUSES,
    terminalScanJobStatuses: TERMINAL_SCAN_JOB_STATUSES,
  }
}
