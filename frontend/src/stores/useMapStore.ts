import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './useAuthStore'

interface VesselPosition {
  mmsi: number
  imo: number | null
  vessel_name: string | null
  vessel_type: string
  latitude: number
  longitude: number
  speed_knots: number | null
  course: number | null
  destination: string | null
  flag_country: string | null
  time: string
}

interface Port {
  id: string
  name: string
  country_code: string
  latitude: number
  longitude: number
  commodities: string[]
  is_major: boolean
  is_chokepoint: boolean
}

interface TradeFlow {
  type: string
  geometry: { type: string; coordinates: number[][] }
  properties: {
    commodity: string
    origin: string
    destination: string
    volume_mt: number | null
    value_usd: number | null
  }
}

export const useMapStore = defineStore('map', () => {
  const vessels = ref<VesselPosition[]>([])
  const ports = ref<Port[]>([])
  const tradeFlows = ref<TradeFlow[]>([])
  const loading = ref(false)
  const selectedVessel = ref<VesselPosition | null>(null)
  const vesselTypeFilter = ref<string | null>(null)
  const commodityFilter = ref<string | null>(null)

  const filteredVessels = computed(() => {
    if (!vesselTypeFilter.value) return vessels.value
    return vessels.value.filter(v => v.vessel_type === vesselTypeFilter.value)
  })

  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  async function getHeaders(): Promise<Record<string, string>> {
    const auth = useAuthStore()
    const token = await auth.getToken()
    return token
      ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' }
  }

  async function fetchVessels(bbox?: string) {
    const headers = await getHeaders()
    const params = new URLSearchParams({ limit: '5000' })
    if (bbox) params.set('bbox', bbox)
    if (vesselTypeFilter.value) params.set('vessel_type', vesselTypeFilter.value)

    try {
      const res = await fetch(`${apiBase}/api/v1/vessels?${params}`, { headers })
      if (res.ok) {
        const body = await res.json()
        vessels.value = body.data
      }
    } catch (e) {
      console.error('Failed to fetch vessels:', e)
    }
  }

  async function fetchPorts() {
    const headers = await getHeaders()
    try {
      const res = await fetch(`${apiBase}/api/v1/ports?is_major=true&limit=500`, { headers })
      if (res.ok) {
        const body = await res.json()
        ports.value = body.data
      }
    } catch (e) {
      console.error('Failed to fetch ports:', e)
    }
  }

  async function fetchTradeFlows() {
    const headers = await getHeaders()
    const params = new URLSearchParams({ limit: '50' })
    if (commodityFilter.value) params.set('commodity', commodityFilter.value)

    try {
      const res = await fetch(`${apiBase}/api/v1/commodities/flows?${params}`, { headers })
      if (res.ok) {
        const body = await res.json()
        tradeFlows.value = body.features
      }
    } catch (e) {
      console.error('Failed to fetch trade flows:', e)
    }
  }

  async function selectVessel(mmsi: number) {
    const headers = await getHeaders()
    try {
      const res = await fetch(`${apiBase}/api/v1/vessels/${mmsi}`, { headers })
      if (res.ok) {
        const body = await res.json()
        selectedVessel.value = body.data
      }
    } catch (e) {
      console.error('Failed to fetch vessel detail:', e)
    }
  }

  function clearSelection() {
    selectedVessel.value = null
  }

  return {
    vessels,
    ports,
    tradeFlows,
    loading,
    selectedVessel,
    vesselTypeFilter,
    commodityFilter,
    filteredVessels,
    fetchVessels,
    fetchPorts,
    fetchTradeFlows,
    selectVessel,
    clearSelection,
  }
})
