type AuthedFetchOptions = Parameters<typeof $fetch>[1]
const AUTH_ERROR_KEY = 'auth_error_message'

type AuthExpiredError = Error & {
  isAuthExpired: true
  statusCode: 401
}

const isUnauthorizedError = (error: unknown) => {
  const candidate = error as {
    status?: number
    statusCode?: number
    response?: { status?: number }
    data?: { status?: number; statusCode?: number }
  }
  return candidate?.status === 401
    || candidate?.statusCode === 401
    || candidate?.response?.status === 401
    || candidate?.data?.status === 401
    || candidate?.data?.statusCode === 401
}

export const isAuthExpiredError = (error: unknown): error is AuthExpiredError => {
  return Boolean((error as AuthExpiredError | undefined)?.isAuthExpired)
}

export const consumeAuthErrorMessage = () => {
  if (!import.meta.client) {
    return ''
  }

  const message = sessionStorage.getItem(AUTH_ERROR_KEY) || ''
  sessionStorage.removeItem(AUTH_ERROR_KEY)
  return message
}

export const useAuthedFetch = () => {
  const config = useRuntimeConfig()
  const { token, clearAuth, setAuthError } = useAuth()
  const { t } = useI18n()

  const authedFetch = async <T>(path: string, options: AuthedFetchOptions = {}) => {
    const headers: Record<string, string> = {
      ...((options?.headers as Record<string, string> | undefined) || {})
    }

    if (token.value) {
      headers.Authorization = `Bearer ${token.value}`
    }

    try {
      return await $fetch<T>(`${config.public.apiBase}${path}`, {
        ...options,
        headers
      })
    } catch (error) {
      if (!isUnauthorizedError(error)) {
        throw error
      }

      if (import.meta.client) {
        sessionStorage.setItem(AUTH_ERROR_KEY, t('auth_relogin_required'))
      }
      setAuthError(t('auth_relogin_required'))
      clearAuth()
      const authError = new Error(t('auth_relogin_required')) as AuthExpiredError
      authError.isAuthExpired = true
      authError.statusCode = 401
      throw authError
    }
  }

  return {
    authedFetch,
  }
}
