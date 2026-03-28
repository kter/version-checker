<template>
  <div class="flex items-center justify-center min-h-[60vh]">
    <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center max-w-sm w-full">
      <div v-if="!error" class="flex flex-col items-center gap-4">
        <div class="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full animate-spin"></div>
        <p class="text-lg font-medium text-gray-900 dark:text-white">{{ $t('auth_wait') }}</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ $t('auth_wait_desc') }}</p>
      </div>
      <div v-else class="flex flex-col items-center gap-4">
        <div class="w-12 h-12 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center">
          <span class="text-2xl">⚠️</span>
        </div>
        <p class="text-lg font-medium text-red-600 dark:text-red-400">{{ $t('auth_failed') }}</p>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ error }}</p>
        <UButton
          color="primary"
          variant="solid"
          size="lg"
          :label="$t('back_to_dashboard')"
          @click="router.push('/')"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()
const { t } = useI18n()
const { setAuth } = useAuth()
const error = ref('')
const isExchanging = ref(false)

onMounted(async () => {
  const rawCode = Array.isArray(route.query.code) ? route.query.code[0] : route.query.code
  const code = typeof rawCode === 'string' ? rawCode : ''

  if (!code) {
    error.value = t('auth_missing_code')
    return
  }

  // Guard against duplicate client-side exchanges for the same one-time GitHub code.
  const exchangeKey = `github_oauth_exchange:${code}`
  if (sessionStorage.getItem(exchangeKey)) {
    error.value = t('auth_code_already_used')
    return
  }

  try {
    isExchanging.value = true
    sessionStorage.setItem(exchangeKey, 'in-flight')
    const response = await $fetch(`${config.public.apiBase}/auth/callback`, {
      query: { code }
    })

    if (response.access_token) {
      sessionStorage.setItem(exchangeKey, 'done')
      setAuth(
        response.access_token,
        response.user?.username || t('default_user'),
        response.organizations || []
      )

      router.push('/')
    } else {
      sessionStorage.removeItem(exchangeKey)
      error.value = response.message || t('auth_generic_failure')
    }
  } catch (err) {
    sessionStorage.removeItem(exchangeKey)
    error.value = err.data?.detail || err.message || t('auth_load_failed')
  } finally {
    isExchanging.value = false
  }
})
</script>
