<template>
  <div class="space-y-8">
    <div class="relative overflow-hidden bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-3xl p-8 sm:p-10 text-white shadow-2xl">
      <div class="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
      <div class="absolute bottom-0 left-0 w-40 h-40 bg-black/10 rounded-full blur-2xl translate-y-1/2 -translate-x-1/2"></div>
      <div class="relative z-10">
        <h2 class="text-3xl sm:text-4xl font-['Outfit'] font-extrabold mb-3 tracking-tight">{{ $t('dashboard') }}</h2>
        <p class="text-white/80 text-lg max-w-2xl">{{ $t('subtitle') }}</p>
      </div>
    </div>

    <div class="flex flex-col gap-4 bg-white/60 dark:bg-gray-900/60 backdrop-blur-xl p-5 rounded-2xl border border-white/20 dark:border-white/5 shadow-sm">
      <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div class="flex flex-col sm:flex-row sm:items-center gap-3 w-full sm:w-auto">
          <label class="text-sm font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">{{ $t('organization') }}:</label>
          <USelect
            v-model="selectedOrg"
            :items="userOrgs"
            label-key="login"
            value-key="login"
            :placeholder="$t('select_org')"
            class="w-full sm:w-64"
            size="lg"
          />
        </div>
        <div class="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400 bg-gray-100/50 dark:bg-gray-800/50 px-3 py-1.5 rounded-lg">
            {{ $t('repositories_found', { count: repositoryCount }) }}
          </p>
          <p class="text-sm font-medium text-gray-500 dark:text-gray-400 bg-gray-100/50 dark:bg-gray-800/50 px-3 py-1.5 rounded-lg">
            {{ $t('selected_repositories', { count: selectedRepositoryCount }) }}
          </p>
        </div>
      </div>

      <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <p class="text-sm font-medium" :class="hasPendingSelectionChanges ? 'text-amber-700 dark:text-amber-300' : 'text-emerald-700 dark:text-emerald-300'">
          {{ hasPendingSelectionChanges ? $t('selection_unsaved') : $t('selection_saved') }}
        </p>
        <div class="flex flex-wrap gap-3 w-full sm:w-auto">
          <UButton
            color="gray"
            variant="ghost"
            size="lg"
            :disabled="!canBulkSelectAll"
            @click="setAllRepositorySelections(true)"
            :label="$t('select_all_repositories')"
          />
          <UButton
            color="gray"
            variant="ghost"
            size="lg"
            :disabled="!canBulkClearAll"
            @click="setAllRepositorySelections(false)"
            :label="$t('clear_all_repositories')"
          />
          <UButton
            color="gray"
            variant="soft"
            size="lg"
            :loading="isSavingSelection"
            :disabled="!canSaveSelection"
            @click="saveSelection"
            :label="$t('save_selection')"
          />
          <UButton
            icon="i-heroicons-arrow-path"
            color="indigo"
            variant="solid"
            size="lg"
            class="shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300"
            :loading="isScanning"
            :disabled="!canScan"
            @click="scanOrganization"
            :label="$t('scan')"
          />
        </div>
      </div>
    </div>

    <div
      v-if="activeJob && isScanJobActive"
      class="bg-amber-50/80 dark:bg-amber-950/70 backdrop-blur-sm border border-amber-200 dark:border-amber-800/50 rounded-2xl p-5 text-amber-900 dark:text-amber-100 shadow-sm"
    >
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="text-sm font-semibold">{{ scanJobStatusLabel }}</p>
          <p class="text-sm text-amber-800/80 dark:text-amber-200/80">
            {{ $t('scan_progress', { completed: activeJob.completed_repos, total: activeJob.total_repos }) }}
          </p>
        </div>
        <p class="text-xs uppercase tracking-[0.18em] text-amber-700/70 dark:text-amber-300/70">
          {{ activeJob.status }}
        </p>
      </div>
    </div>

    <div v-if="error" class="animate-[fadeIn_0.3s_ease-out] bg-red-50/80 dark:bg-red-950/80 backdrop-blur-sm border border-red-200 dark:border-red-800/50 rounded-2xl p-5 text-red-700 dark:text-red-300 text-sm flex items-center gap-3 mb-6 shadow-sm">
      <span class="text-xl">⚠️</span>
      <span class="font-medium">{{ error }}</span>
    </div>

    <div v-if="repositories.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      <div
        v-for="repo in repositories"
        :key="repo.repository_id"
        class="group relative bg-white/60 dark:bg-gray-900/60 backdrop-blur-md rounded-2xl p-6 border border-white/20 dark:border-white/5 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 overflow-hidden"
      >
        <div
          class="absolute inset-x-0 top-0 h-1 bg-gradient-to-r"
          :class="repo.framework ? (repo.is_eol ? 'from-red-500 to-rose-500' : 'from-emerald-400 to-cyan-500') : 'from-slate-300 to-slate-400 dark:from-slate-700 dark:to-slate-600'"
        ></div>

        <div class="flex justify-between items-start gap-4 mb-4">
          <div class="min-w-0 flex-1">
            <label class="inline-flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                :checked="repo.is_selected"
                :disabled="isSavingSelection || isScanJobActive"
                @change="toggleRepositorySelection(repo.repository_id)"
              >
              <span class="text-sm font-semibold text-gray-900 dark:text-white truncate" :title="repo.repo_id">
                {{ repo.repo_id }}
              </span>
            </label>
          </div>
          <UBadge
            :color="repo.is_selected ? 'indigo' : 'gray'"
            variant="subtle"
            size="sm"
            class="font-semibold shadow-sm whitespace-nowrap"
          >
            {{ repo.is_selected ? $t('monitoring_enabled') : $t('monitoring_disabled') }}
          </UBadge>
        </div>

        <div class="space-y-3">
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_framework') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">
              {{ repo.framework || $t('not_scanned_yet') }}
            </span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_version') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">
              {{ repo.version || $t('not_scanned_yet') }}
            </span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_status') }}</span>
            <span class="font-medium text-right" :class="repo.framework ? (repo.is_eol ? 'text-red-600 dark:text-red-300' : 'text-emerald-600 dark:text-emerald-300') : 'text-gray-500 dark:text-gray-400'">
              {{ repo.framework ? (repo.is_eol ? $t('status_eol') : $t('status_supported')) : $t('scan_status_pending') }}
            </span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_source_path') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right break-all">
              {{ repo.source_path || '-' }}
            </span>
          </div>
          <div v-if="repo.eol_date" class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_eol_date') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100">{{ new Date(repo.eol_date).toLocaleDateString() }}</span>
          </div>
        </div>

        <div class="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
          <span>{{ $t('col_last_scanned') }}</span>
          <span class="text-right">{{ repo.last_scanned_at ? new Date(repo.last_scanned_at).toLocaleString() : $t('not_scanned_yet') }}</span>
        </div>
      </div>
    </div>

    <div v-else-if="!isLoading" class="bg-white/50 dark:bg-gray-900/50 backdrop-blur-md rounded-3xl border border-white/20 dark:border-white/5 py-24 text-center shadow-sm">
      <div class="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-900 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-inner">
        <span class="text-4xl">📦</span>
      </div>
      <h3 class="text-xl font-bold text-gray-900 dark:text-white mb-2 font-['Outfit']">{{ $t('no_repositories') }}</h3>
      <p class="text-gray-500 dark:text-gray-400 max-w-md mx-auto">{{ $t('no_repositories_desc') }}</p>
    </div>

    <div v-if="isLoading && repositories.length === 0" class="py-24 text-center">
      <UIcon name="i-heroicons-arrow-path" class="w-10 h-10 animate-spin text-indigo-500 mx-auto mb-4" />
      <p class="text-gray-500 dark:text-gray-400">{{ $t('loading_repositories') }}</p>
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig()
const { organizations, syncFromStorage } = useAuth()
const { t } = useI18n()

const isScanning = ref(false)
const isSavingSelection = ref(false)
const isLoading = ref(false)
const error = ref('')
const repositories = ref([])
const repositoryCount = ref(0)
const activeJob = ref(null)
const pollingHandle = ref(null)
const savedSelectedRepoIds = ref([])

const userOrgs = computed(() => organizations.value)
const selectedOrg = ref('')

const ACTIVE_SCAN_JOB_STATUSES = new Set(['queued', 'running'])
const TERMINAL_SCAN_JOB_STATUSES = new Set(['completed', 'partial_failed', 'failed'])

const selectedRepositoryIds = computed(() => {
  return repositories.value
    .filter(repo => repo.is_selected)
    .map(repo => repo.repository_id)
    .sort()
})

const selectedRepositoryCount = computed(() => selectedRepositoryIds.value.length)
const allRepositoriesSelected = computed(() => {
  return repositories.value.length > 0 && selectedRepositoryCount.value === repositories.value.length
})
const noRepositoriesSelected = computed(() => selectedRepositoryCount.value === 0)

const hasPendingSelectionChanges = computed(() => {
  return JSON.stringify(selectedRepositoryIds.value) !== JSON.stringify([...savedSelectedRepoIds.value].sort())
})

const isScanJobActive = computed(() => {
  return Boolean(activeJob.value && ACTIVE_SCAN_JOB_STATUSES.has(activeJob.value.status))
})

const canSaveSelection = computed(() => {
  return Boolean(selectedOrg.value && hasPendingSelectionChanges.value && !isSavingSelection.value && !isScanJobActive.value)
})

const canBulkSelectAll = computed(() => {
  return Boolean(
    selectedOrg.value &&
    repositories.value.length > 0 &&
    !isSavingSelection.value &&
    !isScanJobActive.value &&
    !allRepositoriesSelected.value
  )
})

const canBulkClearAll = computed(() => {
  return Boolean(
    selectedOrg.value &&
    repositories.value.length > 0 &&
    !isSavingSelection.value &&
    !isScanJobActive.value &&
    !noRepositoriesSelected.value
  )
})

const canScan = computed(() => {
  return Boolean(selectedOrg.value && !isScanJobActive.value && !hasPendingSelectionChanges.value && selectedRepositoryCount.value > 0)
})

const scanJobStatusLabel = computed(() => {
  if (!activeJob.value) {
    return ''
  }
  if (activeJob.value.status === 'queued') {
    return t('scan_queued')
  }
  return t('scan_running')
})

function initializeSelectedOrg() {
  if (userOrgs.value.length === 0) {
    selectedOrg.value = ''
    repositories.value = []
    repositoryCount.value = 0
    savedSelectedRepoIds.value = []
    stopPolling()
    activeJob.value = null
    return
  }

  const orgStillSelected = userOrgs.value.some(org => org.login === selectedOrg.value)
  if (!orgStillSelected) {
    selectedOrg.value = userOrgs.value[0].login
  }

  if (selectedOrg.value) {
    loadData()
  }
}

onMounted(() => {
  syncFromStorage()
})

watch(
  userOrgs,
  () => {
    initializeSelectedOrg()
  },
  { deep: true, immediate: true }
)

watch(selectedOrg, (newValue, oldValue) => {
  if (newValue && newValue !== oldValue) {
    stopPolling()
    loadData()
  }
})

onUnmounted(() => {
  stopPolling()
})

function stopPolling() {
  if (pollingHandle.value) {
    clearInterval(pollingHandle.value)
    pollingHandle.value = null
  }
}

function syncJobState(job) {
  activeJob.value = job || null
  isScanning.value = Boolean(job && ACTIVE_SCAN_JOB_STATUSES.has(job.status))
  if (job && ACTIVE_SCAN_JOB_STATUSES.has(job.status)) {
    startPolling(job.job_id)
    return
  }
  stopPolling()
}

function startPolling(jobId) {
  if (pollingHandle.value) return
  pollingHandle.value = setInterval(() => {
    pollJobStatus(jobId)
  }, 3000)
}

function applyRepositoryResponse(response) {
  repositories.value = response.repositories || []
  repositoryCount.value = response.repository_count ?? response.repositories?.length ?? 0
  savedSelectedRepoIds.value = repositories.value
    .filter(repo => repo.is_selected)
    .map(repo => repo.repository_id)
}

function toggleRepositorySelection(repositoryId) {
  repositories.value = repositories.value.map((repo) => {
    if (repo.repository_id !== repositoryId) {
      return repo
    }
    return {
      ...repo,
      is_selected: !repo.is_selected
    }
  })
}

function setAllRepositorySelections(isSelected) {
  repositories.value = repositories.value.map(repo => ({
    ...repo,
    is_selected: isSelected
  }))
}

async function pollJobStatus(jobId) {
  if (!selectedOrg.value) return
  try {
    const token = localStorage.getItem('auth_token')
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${selectedOrg.value}/jobs/${jobId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    syncJobState(response)
    if (TERMINAL_SCAN_JOB_STATUSES.has(response.status)) {
      isScanning.value = false
      const terminalError = response.status === 'partial_failed' || response.status === 'failed'
        ? (response.error_message || t('scan_failed_message'))
        : ''
      await loadData({ preserveExisting: true, clearError: !terminalError })
      if (terminalError) {
        error.value = terminalError
      }
    }
  } catch (err) {
    stopPolling()
    isScanning.value = false
    if (err.data?.detail) {
      error.value = err.data.detail
    } else {
      error.value = err.message || t('scan_failed_message')
    }
  }
}

async function loadData(options = {}) {
  if (!selectedOrg.value) return
  const { preserveExisting = false, clearError = true } = options
  isLoading.value = true
  if (clearError) {
    error.value = ''
  }
  if (!preserveExisting) {
    repositories.value = []
  }
  try {
    const token = localStorage.getItem('auth_token')
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${selectedOrg.value}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    applyRepositoryResponse(response)
    syncJobState(response.latest_job)
  } catch (err) {
    if (err.data?.detail) {
      error.value = err.data.detail
    } else {
      error.value = err.message || t('load_repositories_failed')
    }
  } finally {
    isLoading.value = false
  }
}

async function saveSelection() {
  if (!canSaveSelection.value) return
  isSavingSelection.value = true
  error.value = ''
  try {
    const token = localStorage.getItem('auth_token')
    await $fetch(`${config.public.apiBase}/scan/orgs/${selectedOrg.value}/selection`, {
      method: 'PUT',
      body: {
        selected_repo_ids: selectedRepositoryIds.value
      },
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    await loadData({ preserveExisting: true })
  } catch (err) {
    if (err.data?.detail) {
      error.value = err.data.detail
    } else {
      error.value = err.message || t('selection_save_failed_message')
    }
  } finally {
    isSavingSelection.value = false
  }
}

async function scanOrganization() {
  if (!canScan.value) return
  isScanning.value = true
  error.value = ''
  try {
    const token = localStorage.getItem('auth_token')
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${selectedOrg.value}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    syncJobState(response)
  } catch (err) {
    isScanning.value = false
    if (err.data?.detail) {
      error.value = err.data.detail
    } else {
      error.value = err.message || t('scan_failed_message')
    }
  }
}
</script>
