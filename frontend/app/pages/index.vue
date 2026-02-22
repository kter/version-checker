<template>
  <div class="space-y-6">
    <!-- Hero Section -->
    <div class="bg-gradient-to-r from-green-600 to-emerald-500 rounded-2xl p-8 text-white shadow-lg">
      <h2 class="text-2xl font-bold mb-2">{{ $t('dashboard') }}</h2>
      <p class="text-green-100 text-sm">{{ $t('subtitle') }}</p>
    </div>

    <!-- Actions Bar -->
    <div class="flex justify-between items-center">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {{ $t('repositories_found', { count: repositories ? repositories.length : 0 }) }}
      </p>
      <UButton
        icon="i-heroicons-arrow-path"
        color="primary"
        variant="solid"
        size="lg"
        :loading="isScanning"
        @click="scanOrganization"
        :label="$t('scan')"
      />
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl p-4 text-red-700 dark:text-red-300 text-sm">
      ⚠️ {{ error }}
    </div>

    <!-- Data Table Card (only shown when there is data) -->
    <div v-if="repositories.length > 0" class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <UTable
        :data="repositories"
        :columns="columns"
        :loading="isLoading"
      >
        <template #is_eol-cell="{ row }">
          <UBadge
            :color="row.original.is_eol ? 'error' : 'success'"
            variant="subtle"
            size="sm"
          >
            {{ row.original.is_eol ? '⛔ EOL' : '✅ Supported' }}
          </UBadge>
        </template>
        <template #eol_date-cell="{ row }">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ row.original.eol_date ? new Date(row.original.eol_date).toLocaleDateString() : '—' }}
          </span>
        </template>
        <template #last_scanned_at-cell="{ row }">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ new Date(row.original.last_scanned_at).toLocaleString() }}
          </span>
        </template>
      </UTable>
    </div>

    <!-- Empty State (only shown when no data) -->
    <div v-if="!isLoading && repositories.length === 0" class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 py-16 text-center">
      <div class="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <span class="text-3xl">📦</span>
      </div>
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-1">{{ $t('no_data') }}</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-6">{{ $t('no_data_desc', { scan: $t('scan') }) }}</p>
      <UButton
        icon="i-heroicons-arrow-path"
        color="primary"
        variant="solid"
        size="lg"
        :loading="isScanning"
        @click="scanOrganization"
        :label="$t('scan')"
      />
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig()
const isScanning = ref(false)
const isLoading = ref(false)
const error = ref('')
const repositories = ref([])

const { t } = useI18n()

const columns = computed(() => [
  { accessorKey: 'repo_id', header: t('col_repository'), id: 'repo_id' },
  { accessorKey: 'framework', header: t('col_framework'), id: 'framework' },
  { accessorKey: 'version', header: t('col_version'), id: 'version' },
  { accessorKey: 'is_eol', header: t('col_status'), id: 'is_eol' },
  { accessorKey: 'eol_date', header: t('col_eol_date'), id: 'eol_date' },
  { accessorKey: 'last_scanned_at', header: t('col_last_scanned'), id: 'last_scanned_at' }
])

// Sample default org ID for demo
const orgId = "org-1"

const loadData = async () => {
  isLoading.value = true
  error.value = ''
  try {
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${orgId}`)
    repositories.value = response.statuses || []
  } catch (err) {
    error.value = err.message || 'Failed to load data'
  } finally {
    isLoading.value = false
  }
}

const scanOrganization = async () => {
  isScanning.value = true
  error.value = ''
  try {
    const response = await $fetch(`${config.public.apiBase}/scan/orgs/${orgId}`, {
      method: 'POST'
    })
    repositories.value = response.statuses || []
  } catch (err) {
    error.value = err.message || 'Failed to trigger scan'
  } finally {
    isScanning.value = false
  }
}

onMounted(() => {
  // loadData() could be called here or wait for manual action
})
</script>
