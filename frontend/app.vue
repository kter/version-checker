<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <UContainer>
      <header class="py-6 flex justify-between items-center">
        <h1 class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
          Version Checker
        </h1>
        <div class="flex items-center gap-4">
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
            :label="$t('login')"
            @click="login"
          />
          <UButton
            v-else
            icon="i-heroicons-arrow-left-on-rectangle"
            color="gray"
            variant="ghost"
            label="Logout"
            @click="logout"
          />
        </div>
      </header>
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

const login = () => {
  // In a real app we'd redirect to backend /api/v1/auth/login
  window.location.href = '/api/v1/auth/login'
}

const logout = () => {
  isAuthenticated.value = false
}
</script>
