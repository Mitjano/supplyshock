import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './useAuthStore'

export interface FleetOwner {
  owner_id: string
  owner_name: string
  vessel_count: number
  total_dwt: number
  utilization: number
  vessels: FleetVessel[]
}

export interface FleetVessel {
  imo: number
  vessel_name: string
  vessel_type: string
  dwt: number
  flag: string
  status: 'laden' | 'ballast' | 'idle' | 'in_port'
  last_position: { lat: number; lng: number } | null
  last_update: string
}

export const useFleetStore = defineStore('fleet', () => {
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  const owners = ref<FleetOwner[]>([])
  const loading = ref(false)
  const error = ref(false)

  async function fetchFleet() {
    loading.value = true
    error.value = false
    try {
      const auth = useAuthStore()
      const token = await auth.getToken()
      const resp = await fetch(`${API_BASE}/api/v1/fleet/owners`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const json = await resp.json()
      owners.value = json.data || []
    } catch {
      error.value = true
    } finally {
      loading.value = false
    }
  }

  async function fetchOwnerDetail(ownerId: string): Promise<FleetOwner | null> {
    try {
      const auth = useAuthStore()
      const token = await auth.getToken()
      const resp = await fetch(`${API_BASE}/api/v1/fleet/owners/${ownerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const json = await resp.json()
      return json.data || null
    } catch {
      return null
    }
  }

  return { owners, loading, error, fetchFleet, fetchOwnerDetail }
})
