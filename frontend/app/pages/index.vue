<template>
  <div class="space-y-8">
    <!-- Hero Section -->
    <div class="relative overflow-hidden bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-3xl p-8 sm:p-10 text-white shadow-2xl">
      <div class="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
      <div class="absolute bottom-0 left-0 w-40 h-40 bg-black/10 rounded-full blur-2xl translate-y-1/2 -translate-x-1/2"></div>
      <div class="relative z-10">
        <h2 class="text-3xl sm:text-4xl font-['Outfit'] font-extrabold mb-3 tracking-tight">{{ $t('dashboard') }}</h2>
        <p class="text-white/80 text-lg max-w-2xl">{{ $t('subtitle') }}</p>
      </div>
    </div>

    <!-- Actions Bar -->
    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white/60 dark:bg-gray-900/60 backdrop-blur-xl p-5 rounded-2xl border border-white/20 dark:border-white/5 shadow-sm">
      <div class="flex flex-col sm:flex-row sm:items-center gap-3 w-full sm:w-auto">
        <label class="text-sm font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">{{ $t('organization') }}:</label>
        <USelect
          :model-value="selectedOrg"
          :items="userOrgs"
          option-attribute="login"
          value-attribute="login"
          :placeholder="$t('select_org')"
          class="w-full sm:w-64"
          size="lg"
          @update:model-value="val => { selectedOrg = val; onOrgChange() }"
        />
      </div>
      <div class="flex items-center justify-between w-full sm:w-auto gap-4">
        <p class="text-sm font-medium text-gray-500 dark:text-gray-400 bg-gray-100/50 dark:bg-gray-800/50 px-3 py-1.5 rounded-lg">
          {{ $t('repositories_found', { count: repositories ? repositories.length : 0 }) }}
        </p>
        <UButton
          icon="i-heroicons-arrow-path"
          color="indigo"
          variant="solid"
          size="lg"
          class="shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300"
          :loading="isScanning"
          :disabled="!selectedOrg"
          @click="scanOrganization"
          :label="$t('scan')"
        />
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="animate-[fadeIn_0.3s_ease-out] bg-red-50/80 dark:bg-red-950/80 backdrop-blur-sm border border-red-200 dark:border-red-800/50 rounded-2xl p-5 text-red-700 dark:text-red-300 text-sm flex items-center gap-3 mb-6 shadow-sm">
      <span class="text-xl">⚠️</span>
      <span class="font-medium">{{ error }}</span>
    </div>

    <!-- Data Cards -->
    <div v-if="repositories.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      <div 
        v-for="repo in repositories" 
        :key="repo.repo_id"
        class="group relative bg-white/60 dark:bg-gray-900/60 backdrop-blur-md rounded-2xl p-6 border border-white/20 dark:border-white/5 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 overflow-hidden"
      >
        <div class="absolute inset-x-0 top-0 h-1 bg-gradient-to-r" :class="repo.is_eol ? 'from-red-500 to-rose-500' : 'from-emerald-400 to-cyan-500'"></div>
        
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-lg font-bold text-gray-900 dark:text-white truncate pr-4" :title="repo.repo_id">
            {{ repo.repo_id }}
          </h3>
          <UBadge
            :color="repo.is_eol ? 'red' : 'emerald'"
            variant="subtle"
            size="sm"
            class="font-semibold shadow-sm"
          >
            {{ repo.is_eol ? $t('status_eol') : $t('status_supported') }}
          </UBadge>
        </div>

        <div class="space-y-3">
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_framework') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100">{{ repo.framework }}</span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_version') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100">{{ repo.version }}</span>
          </div>
          <div v-if="repo.eol_date" class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">{{ $t('col_eol_date') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100">{{ new Date(repo.eol_date).toLocaleDateString() }}</span>
          </div>
        </div>

        <div class="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
          <span>{{ $t('col_last_scanned') }}</span>
          <span class="text-right">{{ new Date(repo.last_scanned_at).toLocaleString() }}</span>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!isLoading && repositories.length === 0" class="bg-white/50 dark:bg-gray-900/50 backdrop-blur-md rounded-3xl border border-white/20 dark:border-white/5 py-24 text-center shadow-sm">
      <div class="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-900 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-inner">
        <span class="text-4xl">📦</span>
      </div>
      <h3 class="text-xl font-bold text-gray-900 dark:text-white mb-2 font-['Outfit']">{{ $t('no_data') }}</h3>
      <p class="text-gray-500 dark:text-gray-400 mb-8 max-w-md mx-auto">{{ $t('no_data_desc', { scan: $t('scan') }) }}</p>
      <UButton
        icon="i-heroicons-arrow-path"
        color="indigo"
        variant="solid"
        size="xl"
        class="shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all duration-300"
        :loading="isScanning"
        :disabled="!selectedOrg"
        @click="scanOrganization"
        :label="$t('scan')"
      />
    </div>
    
    <!-- Loading Overlay -->
    <div v-if="isLoading && repositories.length === 0" class="py-24 text-center">
      <UIcon name="i-heroicons-arrow-path" class="w-10 h-10 animate-spin text-indigo-500 mx-auto mb-4" />
      <p class="text-gray-500 dark:text-gray-400">{{ $t('loading_repositories') }}</p>
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig()
const { organizations, syncFromStorage } = useAuth()
const isScanning = ref(false)
const isLoading = ref(false)
const error = ref('')
const repositories = ref([])

const userOrgs = computed(() => organizations.value)
const selectedOrg = ref('')

const { t } = useI18n()

function initializeSelectedOrg() {
  if (userOrgs.value.length === 0) {
    selectedOrg.value = ''
    repositories.value = []
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

function onOrgChange() {
  if (selectedOrg.value) {
    loadData()
  }
}

async function loadData() {
  if (!selectedOrg.value) return
  isLoading.value = true
  error.value = ''
  repositories.value = []
  try {
    const token = localStorage.getItem('auth_token')
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${selectedOrg.value}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    repositories.value = response.statuses || []
  } catch (err) {
    if (err.data?.detail) {
      error.value = err.data.detail
    } else {
      error.value = err.message || 'Failed to load data'
    }
  } finally {
    isLoading.value = false
  }
}

async function scanOrganization() {
  if (!selectedOrg.value) return
  isScanning.value = true
  error.value = ''
  try {
    const token = localStorage.getItem('auth_token')
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${selectedOrg.value}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    repositories.value = response.statuses || []
  } catch (err) {
    if (err.data?.detail) {
      error.value = err.data.detail
    } else {
      error.value = err.message || 'Failed to trigger scan'
    }
  } finally {
    isScanning.value = false
  }
}
</script>
