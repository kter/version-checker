<template>
  <div class="space-y-6">
    <!-- Hero Section -->
    <div class="bg-gradient-to-r from-green-600 to-emerald-500 rounded-2xl p-8 text-white shadow-lg">
      <h2 class="text-2xl font-bold mb-2">{{ $t('dashboard') }}</h2>
      <p class="text-green-100 text-sm">Monitor framework versions and EOL status across your repositories.</p>
    </div>

    <!-- Actions Bar -->
    <div class="flex justify-between items-center">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {{ repositories.length }} repositories found
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

    <!-- Data Table Card -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <UTable
        :rows="repositories"
        :columns="columns"
        :loading="isLoading"
      >
        <template #is_eol-data="{ row }">
          <UBadge
            :color="row.is_eol ? 'error' : 'success'"
            variant="subtle"
            size="sm"
          >
            {{ row.is_eol ? '⛔ EOL' : '✅ Supported' }}
          </UBadge>
        </template>
        <template #eol_date-data="{ row }">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ row.eol_date ? new Date(row.eol_date).toLocaleDateString() : '—' }}
          </span>
        </template>
        <template #last_scanned_at-data="{ row }">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ new Date(row.last_scanned_at).toLocaleString() }}
          </span>
        </template>
      </UTable>

      <!-- Empty State -->
      <div v-if="!isLoading && repositories.length === 0" class="py-16 text-center">
        <div class="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <span class="text-3xl">📦</span>
        </div>
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-1">No repositories scanned</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6">Click "{{ $t('scan') }}" above to start scanning your repositories.</p>
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
  </div>
</template>

<script setup>
const config = useRuntimeConfig()
const isScanning = ref(false)
const isLoading = ref(false)
const error = ref('')
const repositories = ref([])

const columns = [
  { accessorKey: 'repo_id', header: 'Repository', id: 'repo_id' },
  { accessorKey: 'framework', header: 'Framework', id: 'framework' },
  { accessorKey: 'version', header: 'Version', id: 'version' },
  { accessorKey: 'is_eol', header: 'Status', id: 'is_eol' },
  { accessorKey: 'eol_date', header: 'EOL Date', id: 'eol_date' },
  { accessorKey: 'last_scanned_at', header: 'Last Scanned', id: 'last_scanned_at' }
]

const { t } = useI18n()

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
