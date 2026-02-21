<template>
  <div>
    <UCard>
      <template #header>
        <div class="flex justify-between items-center">
          <h2 class="text-xl font-semibold">{{ $t('dashboard') }}</h2>
          <UButton
            icon="i-heroicons-arrow-path"
            color="primary"
            :loading="isScanning"
            @click="scanOrganization"
            :label="$t('scan')"
          />
        </div>
      </template>

      <div v-if="error" class="text-red-500 mb-4">
        {{ error }}
      </div>

      <UTable
        :rows="repositories"
        :columns="columns"
        :loading="isLoading"
      >
        <template #is_eol-data="{ row }">
          <UBadge
            :color="row.is_eol ? 'red' : 'green'"
            variant="subtle"
          >
            {{ row.is_eol ? 'EOL' : 'Supported' }}
          </UBadge>
        </template>
        <template #eol_date-data="{ row }">
          {{ row.eol_date ? new Date(row.eol_date).toLocaleDateString() : 'N/A' }}
        </template>
        <template #last_scanned_at-data="{ row }">
          {{ new Date(row.last_scanned_at).toLocaleString() }}
        </template>
      </UTable>
    </UCard>
  </div>
</template>

<script setup>
const config = useRuntimeConfig()
const isScanning = ref(false)
const isLoading = ref(false)
const error = ref('')
const repositories = ref([])

const columns = [
  { key: 'repo_id', label: 'Repository ID' },
  { key: 'framework', label: 'Framework' },
  { key: 'version', label: 'Version' },
  { key: 'is_eol', label: 'Status' },
  { key: 'eol_date', label: 'EOL Date' },
  { key: 'last_scanned_at', label: 'Last Scanned' }
]

const { t } = useI18n()

// Sample default org ID for demo
const orgId = "org-1"

const loadData = async () => {
  isLoading.value = true
  error.value = ''
  try {
    // Note: Since this is purely internal we just fetch from backend API
    // Ensure you use cross-env Nuxt proxy or pass absolute URLs in fetch
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
      method: 'POST' // Trigger a rescan
    })
    repositories.value = response.statuses || []
  } catch (err) {
    error.value = err.message || 'Failed to trigger scan'
  } finally {
    isScanning.value = false
  }
}

onMounted(() => {
  // loadData() could be called here or wait for manual action based on requirements
})
</script>
