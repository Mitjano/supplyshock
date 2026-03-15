import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type Clerk from '@clerk/clerk-js'

interface User {
  id: string
  clerk_user_id: string
  email: string
  name: string | null
  avatar_url: string | null
  plan: string
  plan_expires_at: string | null
  onboarding_completed_steps: Record<string, boolean>
  created_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(true)
  const clerk = ref<Clerk | null>(null)

  const isAuthenticated = computed(() => !!user.value)
  const plan = computed(() => user.value?.plan ?? 'free')
  const isPro = computed(() => ['pro', 'business', 'enterprise'].includes(plan.value))

  async function initClerk() {
    const { default: ClerkJS } = await import('@clerk/clerk-js')
    const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

    if (!publishableKey) {
      console.error('Missing VITE_CLERK_PUBLISHABLE_KEY')
      loading.value = false
      return
    }

    const instance = new ClerkJS(publishableKey)
    await instance.load()
    clerk.value = instance

    if (instance.user) {
      await syncAndFetchUser()
    }

    // Listen for sign-in/out changes
    instance.addListener(async (event) => {
      if (event.user) {
        await syncAndFetchUser()
      } else {
        user.value = null
      }
    })

    loading.value = false
  }

  async function getToken(): Promise<string | null> {
    if (!clerk.value?.session) return null
    return await clerk.value.session.getToken() ?? null
  }

  async function syncAndFetchUser() {
    const token = await getToken()
    if (!token) return

    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

    // Sync user to backend DB
    await fetch(`${apiBase}/api/v1/auth/sync`, { method: 'POST', headers })

    // Fetch full user profile
    const res = await fetch(`${apiBase}/api/v1/auth/me`, { headers })
    if (res.ok) {
      const body = await res.json()
      user.value = body.data
    }
  }

  async function signIn() {
    if (!clerk.value) return
    clerk.value.openSignIn()
  }

  async function signUp() {
    if (!clerk.value) return
    clerk.value.openSignUp()
  }

  async function signOut() {
    if (!clerk.value) return
    await clerk.value.signOut()
    user.value = null
  }

  return {
    user,
    loading,
    clerk,
    isAuthenticated,
    plan,
    isPro,
    initClerk,
    getToken,
    signIn,
    signUp,
    signOut,
  }
})
