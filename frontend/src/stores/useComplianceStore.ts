import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './useAuthStore'

export interface FlaggedVessel {
  mmsi: number
  imo: number | null
  vessel_name: string
  sanction_source: string
  program: string
  match_type: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  flagged_at: string
}

export interface AisGap {
  mmsi: number
  vessel_name: string
  last_seen_lat: number
  last_seen_lon: number
  last_seen_time: string
  reappeared_lat: number
  reappeared_lon: number
  reappeared_time: string
  gap_hours: number
  distance_nm: number
}

export interface StsEvent {
  vessel_a_name: string
  vessel_a_mmsi: number
  vessel_b_name: string
  vessel_b_mmsi: number
  latitude: number
  longitude: number
  detected_at: string
  vessel_a_laden: boolean | null
  vessel_b_laden: boolean | null
}

export const useComplianceStore = defineStore('compliance', () => {
  const flaggedVessels = ref<FlaggedVessel[]>([])
  const aisGaps = ref<AisGap[]>([])
  const stsEvents = ref<StsEvent[]>([])

  const loadingFlagged = ref(false)
  const loadingAisGaps = ref(false)
  const loadingSts = ref(false)

  const errorFlagged = ref(false)
  const errorAisGaps = ref(false)
  const errorSts = ref(false)

  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  async function getHeaders(): Promise<Record<string, string>> {
    const auth = useAuthStore()
    const token = await auth.getToken()
    return token
      ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' }
  }

  async function fetchFlagged(severity?: string) {
    loadingFlagged.value = true
    errorFlagged.value = false
    try {
      const headers = await getHeaders()
      const params = new URLSearchParams()
      if (severity) params.set('severity', severity)
      const res = await fetch(`${apiBase}/api/v1/compliance/flagged?${params}`, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = await res.json()
      flaggedVessels.value = body.data
    } catch (e) {
      console.error('Failed to fetch flagged vessels:', e)
      errorFlagged.value = true
    } finally {
      loadingFlagged.value = false
    }
  }

  async function fetchAisGaps(hours: number = 24) {
    loadingAisGaps.value = true
    errorAisGaps.value = false
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/api/v1/compliance/ais-gaps?hours=${hours}`, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = await res.json()
      aisGaps.value = body.data
    } catch (e) {
      console.error('Failed to fetch AIS gaps:', e)
      errorAisGaps.value = true
    } finally {
      loadingAisGaps.value = false
    }
  }

  async function fetchStsEvents(hours: number = 48) {
    loadingSts.value = true
    errorSts.value = false
    try {
      const headers = await getHeaders()
      const res = await fetch(`${apiBase}/api/v1/compliance/sts-events?hours=${hours}`, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = await res.json()
      stsEvents.value = body.data
    } catch (e) {
      console.error('Failed to fetch STS events:', e)
      errorSts.value = true
    } finally {
      loadingSts.value = false
    }
  }

  return {
    flaggedVessels,
    aisGaps,
    stsEvents,
    loadingFlagged,
    loadingAisGaps,
    loadingSts,
    errorFlagged,
    errorAisGaps,
    errorSts,
    fetchFlagged,
    fetchAisGaps,
    fetchStsEvents,
  }
})
