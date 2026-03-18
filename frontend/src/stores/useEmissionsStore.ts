import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'

export interface EmissionsData {
  vessel_name: string
  mmsi: number
  co2_tonnes: number
  distance_nm: number
  fuel_consumption_mt: number
  eeoi: number
  cii_rating: string
}

export interface FleetEmissionsSummary {
  total_co2: number
  avg_eeoi: number
  cii_distribution: Record<string, number>
  trend_monthly: { month: string; co2: number }[]
}

export const useEmissionsStore = defineStore('emissions', () => {
  const api = useApi()
  const vessels = ref<EmissionsData[]>([])
  const summary = ref<FleetEmissionsSummary | null>(null)
  const loading = ref(false)
  const error = ref(false)
  const timeRange = ref('3M')

  async function fetchEmissions() {
    loading.value = true
    error.value = false
    try {
      const [vesselRes, summaryRes] = await Promise.allSettled([
        api.get<{ data: EmissionsData[] }>('/analytics/emissions/vessels'),
        api.get<{ data: FleetEmissionsSummary }>('/analytics/emissions/summary', { range: timeRange.value }),
      ])

      if (vesselRes.status === 'fulfilled') vessels.value = vesselRes.value.data
      if (summaryRes.status === 'fulfilled') summary.value = summaryRes.value.data
    } catch (e) {
      error.value = true
      console.error('Failed to fetch emissions data:', e)
    } finally {
      loading.value = false
    }
  }

  return {
    vessels,
    summary,
    loading,
    error,
    timeRange,
    fetchEmissions,
  }
})
