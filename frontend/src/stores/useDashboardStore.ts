import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'

export interface DashboardKPIs {
  topMover: { commodity: string; change: number } | null
  activeAlerts: number
  vesselsTracked: number
  watchlistCount: number
}

export interface HeatmapTile {
  commodity: string
  change_24h: number
  price: number
}

export const useDashboardStore = defineStore('dashboard', () => {
  const api = useApi()
  const kpis = ref<DashboardKPIs>({
    topMover: null,
    activeAlerts: 0,
    vesselsTracked: 0,
    watchlistCount: 0,
  })
  const recentAlerts = ref<any[]>([])
  const heatmapData = ref<HeatmapTile[]>([])
  const activeVoyages = ref<{ status: string; count: number }[]>([])
  const newsFeed = ref<any[]>([])
  const loading = ref(false)

  async function fetchDashboard() {
    loading.value = true
    try {
      const [alertRes, pricesRes, statsRes] = await Promise.allSettled([
        api.get<{ data: any[]; meta: { total: number } }>('/alerts', { limit: '5', hours: '24' }),
        api.get<{ data: any[] }>('/commodities/prices'),
        api.get<any>('/alerts/stats', { hours: '24' }),
      ])

      if (alertRes.status === 'fulfilled') {
        recentAlerts.value = alertRes.value.data
        kpis.value.activeAlerts = alertRes.value.meta.total
      }

      if (pricesRes.status === 'fulfilled') {
        const prices = pricesRes.value.data
        heatmapData.value = prices.map((p: any) => ({
          commodity: p.commodity,
          change_24h: p.change_24h ?? 0,
          price: p.price,
        }))

        // Top mover
        if (prices.length > 0) {
          const sorted = [...prices].sort((a: any, b: any) =>
            Math.abs(b.change_24h ?? 0) - Math.abs(a.change_24h ?? 0)
          )
          kpis.value.topMover = {
            commodity: sorted[0].commodity,
            change: sorted[0].change_24h ?? 0,
          }
        }
      }
    } catch (e) {
      console.error('Failed to fetch dashboard data:', e)
    } finally {
      loading.value = false
    }
  }

  return {
    kpis,
    recentAlerts,
    heatmapData,
    activeVoyages,
    newsFeed,
    loading,
    fetchDashboard,
  }
})
