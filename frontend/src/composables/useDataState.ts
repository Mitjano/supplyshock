import { ref, computed, type Ref } from 'vue'

export type DataState = 'idle' | 'loading' | 'success' | 'error' | 'empty'

export function useDataState<T>(initialData?: T) {
  const data = ref<T | undefined>(initialData) as Ref<T | undefined>
  const error = ref<string | null>(null)
  const loading = ref(false)
  const lastUpdated = ref<Date | null>(null)

  const state = computed<DataState>(() => {
    if (loading.value) return 'loading'
    if (error.value) return 'error'
    if (data.value === undefined || data.value === null) return 'idle'
    if (Array.isArray(data.value) && data.value.length === 0) return 'empty'
    return 'success'
  })

  async function execute<R>(fn: () => Promise<R>, transform?: (result: R) => T) {
    loading.value = true
    error.value = null
    try {
      const result = await fn()
      data.value = transform ? transform(result) : (result as unknown as T)
      lastUpdated.value = new Date()
    } catch (e: any) {
      error.value = e.message || 'An error occurred'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    data.value = undefined
    error.value = null
    loading.value = false
    lastUpdated.value = null
  }

  return {
    data,
    error,
    loading,
    lastUpdated,
    state,
    execute,
    reset,
  }
}
