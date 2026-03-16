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
  heading: number | null
  destination: string | null
  flag_country: string | null
  dwt: number | null
  draught: number | null
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

interface Bottleneck {
  slug: string
  name: string
  type: string
  country: string
  risk: number
  vessel_count: number | null
  latitude: number | null
  longitude: number | null
}

interface Alert {
  id: string
  title: string
  severity: string
  type: string
  commodity: string | null
  region: string | null
  created_at: string
}

interface TrailPoint {
  latitude: number
  longitude: number
  time: string
  speed_knots: number | null
}

export const useMapStore = defineStore('map', () => {
  const vessels = ref<VesselPosition[]>([])
  const ports = ref<Port[]>([])
  const tradeFlows = ref<TradeFlow[]>([])
  const bottlenecks = ref<Bottleneck[]>([])
  const alerts = ref<Alert[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedVessel = ref<VesselPosition | null>(null)
  const vesselTypeFilter = ref<string | null>(null)
  const commodityFilter = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)
  const vesselTrail = ref<TrailPoint[]>([])
  const trailLoading = ref(false)

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
        lastUpdated.value = new Date()
        error.value = null
      } else {
        throw new Error(`HTTP ${res.status}`)
      }
    } catch (e) {
      console.error('Failed to fetch vessels:', e)
      error.value = 'vessels'
      throw e
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
      throw e
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
      throw e
    }
  }

  async function fetchBottlenecks() {
    const headers = await getHeaders()
    try {
      const res = await fetch(`${apiBase}/api/v1/bottlenecks`, { headers })
      if (res.ok) {
        const body = await res.json()
        bottlenecks.value = body.data
      } else {
        throw new Error(`HTTP ${res.status}`)
      }
    } catch (e) {
      console.error('Failed to fetch bottlenecks:', e)
      throw e
    }
  }

  async function fetchAlerts(limit = 10) {
    const headers = await getHeaders()
    try {
      const res = await fetch(`${apiBase}/api/v1/alerts?limit=${limit}`, { headers })
      if (res.ok) {
        const body = await res.json()
        alerts.value = body.data
      } else {
        throw new Error(`HTTP ${res.status}`)
      }
    } catch (e) {
      console.error('Failed to fetch alerts:', e)
      throw e
    }
  }

  async function fetchVesselTrail(mmsi: number) {
    const headers = await getHeaders()
    trailLoading.value = true
    try {
      const res = await fetch(`${apiBase}/api/v1/vessels/${mmsi}/trail`, { headers })
      if (res.ok) {
        const body = await res.json()
        vesselTrail.value = body.data
      } else {
        throw new Error(`HTTP ${res.status}`)
      }
    } catch (e) {
      console.error('Failed to fetch vessel trail:', e)
      throw e
    } finally {
      trailLoading.value = false
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
    vesselTrail.value = []
  }

  return {
    vessels,
    ports,
    tradeFlows,
    bottlenecks,
    alerts,
    loading,
    error,
    selectedVessel,
    vesselTypeFilter,
    commodityFilter,
    lastUpdated,
    vesselTrail,
    trailLoading,
    filteredVessels,
    fetchVessels,
    fetchPorts,
    fetchTradeFlows,
    fetchBottlenecks,
    fetchAlerts,
    fetchVesselTrail,
    selectVessel,
    clearSelection,
  }
})
