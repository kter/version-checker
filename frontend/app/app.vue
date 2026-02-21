<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900">
    <!-- Navigation Bar -->
    <nav class="border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <UContainer>
        <div class="py-4 flex justify-between items-center">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center shadow-sm">
              <span class="text-white text-sm font-bold">V</span>
            </div>
            <h1 class="text-xl font-bold tracking-tight text-gray-900 dark:text-white">
              Version Checker
            </h1>
          </div>
          <div class="flex items-center gap-3">
            <!-- Locale Switcher -->
            <USelect
              v-model="locale"
              :options="availableLocales"
              option-attribute="name"
              value-attribute="code"
              size="sm"
            />
            <UButton
              v-if="!isAuthenticated"
              icon="i-heroicons-arrow-right-on-rectangle"
              color="primary"
              variant="solid"
              size="md"
              :label="$t('login')"
              @click="login"
            />
            <UButton
              v-else
              icon="i-heroicons-arrow-left-on-rectangle"
              color="neutral"
              variant="outline"
              size="md"
              label="Logout"
              @click="logout"
            />
          </div>
        </div>
      </UContainer>
    </nav>

    <!-- Main Content -->
    <UContainer>
      <main class="py-8">
        <NuxtPage />
      </main>
    </UContainer>
  </div>
</template>

<script setup>
const { locale, locales } = useI18n()
const availableLocales = computed(() => locales.value)

// Mock authentication state for now
const isAuthenticated = ref(false)

const config = useRuntimeConfig()
const login = () => {
  // Redirect to FastAPI backend OAuth login endpoint
  window.location.href = `${config.public.apiBase}/auth/login`
}

const logout = () => {
  isAuthenticated.value = false
}
</script>
