<template>
  <div class="flex items-center justify-center min-h-screen">
    <UCard>
      <div class="flex flex-col items-center gap-4">
        <UIcon name="i-heroicons-arrow-path" class="w-8 h-8 animate-spin text-primary" />
        <p class="text-lg font-medium">Authenticating with GitHub...</p>
        <p v-if="error" class="text-red-500">{{ error }}</p>
      </div>
    </UCard>
  </div>
</template>

<script setup>
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()
const error = ref('')

onMounted(async () => {
  const code = route.query.code
  if (!code) {
    error.value = 'No authentication code provided'
    return
  }

  try {
    // Exchange the code for a token through the backend API
    const response = await $fetch(`${config.public.apiBase}/auth/callback?code=${code}`)
    
    // In a real app we'd store the token (e.g., in a secure cookie or Vuex/Pinia state)
    // For this demonstration, we'll store it in localStorage
    if (response.access_token) {
      localStorage.setItem('auth_token', response.access_token)
      // Redirect to the dashboard
      router.push('/')
    } else {
      error.value = response.message || 'Authentication failed'
    }
  } catch (err) {
    error.value = err.message || 'Failed to authenticate'
  }
})
</script>
