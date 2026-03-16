import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './useAuthStore'

export interface Bottleneck {
  slug: string
  name: string
  latitude: number
  longitude: number
  node_type: string
  commodities: string[]
  throughput_description: string | null
  risk_level: string
  vessel_count: number | null
}

export interface BottleneckDetail extends Bottleneck {
  congestion_index: number | null
  avg_speed: number | null
  status_history: BottleneckStatus[]
}

export interface BottleneckStatus {
  timestamp: string
  vessel_count: number
  avg_speed: number | null
  congestion_index: number | null
}

export const useBottleneckStore = defineStore('bottleneck', () => {
  const bottlenecks = ref<Bottleneck[]>([])
  const selectedBottleneck = ref<BottleneckDetail | null>(null)
  const loading = ref(false)

  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  async function getHeaders(): Promise<Record<string, string>> {
    const auth = useAuthStore()
    const token = await auth.getToken()
    return token
      ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' }
  }

  const sortedByRisk = computed(() => {
    const order: Record<string, number> = { critical: 0, high: 1, elevated: 2, normal: 3 }
    return [...bottlenecks.value].sort(
      (a, b) => (order[a.risk_level] ?? 4) - (order[b.risk_level] ?? 4)
    )
  })

  async function fetchBottlenecks() {
    const headers = await getHeaders()
    try {
      const res = await fetch(`${apiBase}/api/v1/bottlenecks`, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = await res.json()
      bottlenecks.value = body.data
    } catch (e) {
      console.error('Failed to fetch bottlenecks:', e)
      throw e
    }
  }

  async function selectBottleneck(slug: string) {
    loading.value = true
    const headers = await getHeaders()
    try {
      const [detailRes, statusRes] = await Promise.all([
        fetch(`${apiBase}/api/v1/bottlenecks/${slug}`, { headers }),
        fetch(`${apiBase}/api/v1/bottlenecks/${slug}/status`, { headers }),
      ])

      if (detailRes.ok && statusRes.ok) {
        const detail = await detailRes.json()
        const status = await statusRes.json()
        selectedBottleneck.value = {
          ...detail.data,
          ...status.data.current,
          status_history: status.data.history || [],
        }
      }
    } catch (e) {
      console.error('Failed to fetch bottleneck detail:', e)
    } finally {
      loading.value = false
    }
  }

  function clearSelection() {
    selectedBottleneck.value = null
  }

  return {
    bottlenecks,
    selectedBottleneck,
    loading,
    sortedByRisk,
    fetchBottlenecks,
    selectBottleneck,
    clearSelection,
  }
})
