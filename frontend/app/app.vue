<template>
  <div class="min-h-screen bg-slate-50 dark:bg-gray-950 font-['Inter'] selection:bg-indigo-500/30 text-slate-900 dark:text-slate-100 transition-colors duration-300">
    <!-- Subtle Background Elements -->
    <div class="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div class="absolute -top-40 -right-40 w-[500px] h-[500px] bg-indigo-500/10 dark:bg-indigo-500/5 blur-3xl rounded-full"></div>
      <div class="absolute top-1/3 -left-20 w-[400px] h-[400px] bg-emerald-500/10 dark:bg-emerald-500/5 blur-3xl rounded-full"></div>
    </div>

    <!-- Navigation Bar -->
    <nav class="sticky top-0 z-50 border-b border-white/20 dark:border-white/5 bg-white/60 dark:bg-gray-950/60 backdrop-blur-xl shadow-sm">
      <UContainer>
        <div class="h-16 flex justify-between items-center">
          <div class="flex items-center gap-3 group cursor-pointer" @click="$router.push('/')">
             <div class="w-9 h-9 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-md transform group-hover:scale-105 transition-all duration-300">
              <span class="text-white text-sm font-['Outfit'] font-bold">VC</span>
            </div>
            <h1 class="text-xl font-['Outfit'] font-bold tracking-[-0.02em] bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-400">
              Version Checker
            </h1>
          </div>
          <div class="flex items-center gap-4">
            <!-- Locale Switcher -->
            <USelect
              :model-value="locale"
              :items="availableLocales"
              label-key="name"
              value-key="code"
              size="sm"
              class="w-32"
              @update:model-value="setLocale"
            />
            
            <!-- Auth Actions -->
            <template v-if="!isAuthenticated">
              <UButton
                icon="i-heroicons-arrow-right-on-rectangle"
                color="indigo"
                variant="solid"
                size="md"
                class="shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300"
                :label="$t('login')"
                @click="login"
              />
            </template>
            <template v-else>
              <div class="flex items-center gap-3 pl-3 border-l border-gray-200 dark:border-gray-800">
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300 hidden sm:block">
                  {{ username }}
                </span>
                <UButton
                  icon="i-heroicons-arrow-left-on-rectangle"
                  color="gray"
                  variant="ghost"
                  size="md"
                  class="hover:bg-gray-100 dark:hover:bg-gray-800"
                  @click="logout"
                />
              </div>
            </template>
          </div>
        </div>
      </UContainer>
    </nav>

    <!-- Main Content -->
    <UContainer class="relative z-10">
      <main class="py-10 animate-[fadeIn_0.5s_ease-out]">
        <NuxtPage />
      </main>
    </UContainer>
  </div>
</template>

<script setup>
const { locale, locales, setLocale } = useI18n()
const availableLocales = computed(() => locales.value)
const { isAuthenticated, username, syncFromStorage, clearAuth } = useAuth()

useHead({
  title: 'Version Checker'
})

const config = useRuntimeConfig()

// Check auth state on mount
onMounted(() => {
  syncFromStorage()
  window.addEventListener('storage', syncFromStorage)
})

onBeforeUnmount(() => {
  window.removeEventListener('storage', syncFromStorage)
})

const login = () => {
  window.location.href = `${config.public.apiBase}/auth/login`
}

const logout = () => {
  clearAuth()
}
</script>
