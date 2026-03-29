type CurrentMonthUsageResponse = {
  total_tokens: number
}

export const useMonthlyTokenUsage = () => {
  const config = useRuntimeConfig()
  const { token } = useAuth()

  const totalTokens = useState<number | null>('usage.currentMonth.totalTokens', () => null)
  const isLoading = useState<boolean>('usage.currentMonth.isLoading', () => false)
  const isReady = useState<boolean>('usage.currentMonth.isReady', () => false)

  const clear = () => {
    totalTokens.value = null
    isLoading.value = false
    isReady.value = false
  }

  const fetchCurrentMonthUsage = async () => {
    if (!import.meta.client || !token.value) {
      clear()
      return
    }

    isLoading.value = true

    try {
      const response = await $fetch<CurrentMonthUsageResponse>(
        `${config.public.apiBase}/usage/current-month`,
        {
          headers: {
            Authorization: `Bearer ${token.value}`
          }
        }
      )
      totalTokens.value = response.total_tokens
    } catch {
      totalTokens.value = null
    } finally {
      isLoading.value = false
      isReady.value = true
    }
  }

  return {
    totalTokens,
    isLoading,
    isReady,
    clear,
    fetchCurrentMonthUsage,
  }
}
