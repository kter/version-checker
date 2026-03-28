type AuthOrganization = {
  id: number | string
  login: string
}

const AUTH_TOKEN_KEY = 'auth_token'
const AUTH_USER_KEY = 'auth_user'
const AUTH_ORGS_KEY = 'auth_orgs'

const parseOrganizations = (raw: string | null): AuthOrganization[] => {
  if (!raw) {
    return []
  }

  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export const useAuth = () => {
  const token = useState<string | null>('auth.token', () => null)
  const username = useState<string>('auth.username', () => '')
  const organizations = useState<AuthOrganization[]>('auth.organizations', () => [])

  const syncFromStorage = () => {
    if (!import.meta.client) {
      return
    }

    token.value = localStorage.getItem(AUTH_TOKEN_KEY)
    username.value = localStorage.getItem(AUTH_USER_KEY) || ''
    organizations.value = parseOrganizations(localStorage.getItem(AUTH_ORGS_KEY))
  }

  const setAuth = (authToken: string, authUsername: string, authOrganizations: AuthOrganization[] = []) => {
    token.value = authToken
    username.value = authUsername
    organizations.value = authOrganizations

    if (!import.meta.client) {
      return
    }

    localStorage.setItem(AUTH_TOKEN_KEY, authToken)
    localStorage.setItem(AUTH_USER_KEY, authUsername)
    localStorage.setItem(AUTH_ORGS_KEY, JSON.stringify(authOrganizations))
  }

  const clearAuth = () => {
    token.value = null
    username.value = ''
    organizations.value = []

    if (!import.meta.client) {
      return
    }

    localStorage.removeItem(AUTH_TOKEN_KEY)
    localStorage.removeItem(AUTH_USER_KEY)
    localStorage.removeItem(AUTH_ORGS_KEY)
  }

  const isAuthenticated = computed(() => Boolean(token.value && username.value))

  return {
    token,
    username,
    organizations,
    isAuthenticated,
    syncFromStorage,
    setAuth,
    clearAuth,
  }
}
