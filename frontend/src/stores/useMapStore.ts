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
    source?: string
  }
}

interface Voyage {
  id: string
  mmsi: number
  imo: number | null
  vessel_name: string | null
  vessel_type: string
  origin: { port_id: string; name: string; country_code: string } | null
  destination: { port_id: string; name: string; country_code: string } | null
  departure_time: string | null
  arrival_time: string | null
  status: string
  laden_status: string | null
  cargo_type: string | null
  volume_estimate: number | null
  distance_nm: number | null
  created_at: string
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
  const voyages = ref<Voyage[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedVessel = ref<VesselPosition | null>(null)
  const selectedVesselVoyage = ref<Voyage | null>(null)
  const vesselTypeFilter = ref<string | null>(null)
  const commodityFilter = ref<string | null>(null)
  const voyageStatusFilter = ref<string | null>(null)
  const ladenFilter = ref<string | null>(null)
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

  async function fetchVoyages(params?: { status?: string; cargo_type?: string; laden_status?: string }) {
    const headers = await getHeaders()
    const searchParams = new URLSearchParams({ limit: '50' })
    if (params?.status || voyageStatusFilter.value) {
      searchParams.set('status', params?.status || voyageStatusFilter.value!)
    }
    if (params?.cargo_type || commodityFilter.value) {
      searchParams.set('cargo_type', params?.cargo_type || commodityFilter.value!)
    }

    try {
      const res = await fetch(`${apiBase}/api/v1/voyages?${searchParams}`, { headers })
      if (res.ok) {
        const body = await res.json()
        voyages.value = body.data
      }
    } catch (e) {
      console.error('Failed to fetch voyages:', e)
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
      // Fetch current voyage for this vessel
      const voyageRes = await fetch(
        `${apiBase}/api/v1/voyages?mmsi=${mmsi}&status=underway&limit=1`, { headers }
      )
      if (voyageRes.ok) {
        const voyageBody = await voyageRes.json()
        selectedVesselVoyage.value = voyageBody.data?.[0] || null
      }
    } catch (e) {
      console.error('Failed to fetch vessel detail:', e)
    }
  }

  function clearSelection() {
    selectedVessel.value = null
    selectedVesselVoyage.value = null
    vesselTrail.value = []
  }

  const floatingStorageVessels = computed(() => {
    return voyages.value.filter(v => v.status === 'floating_storage')
  })

  const underwayVoyages = computed(() => {
    return voyages.value.filter(v => v.status === 'underway')
  })

  return {
    vessels,
    ports,
    tradeFlows,
    bottlenecks,
    alerts,
    voyages,
    loading,
    error,
    selectedVessel,
    selectedVesselVoyage,
    vesselTypeFilter,
    commodityFilter,
    voyageStatusFilter,
    ladenFilter,
    lastUpdated,
    vesselTrail,
    trailLoading,
    filteredVessels,
    floatingStorageVessels,
    underwayVoyages,
    fetchVessels,
    fetchPorts,
    fetchTradeFlows,
    fetchBottlenecks,
    fetchAlerts,
    fetchVoyages,
    fetchVesselTrail,
    selectVessel,
    clearSelection,
  }
})
