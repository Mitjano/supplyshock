import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './useAuthStore'

export interface CommodityPrice {
  commodity: string
  benchmark: string
  price: number
  unit: string
  change_24h: number | null
  timestamp: string
}

export interface PriceHistoryPoint {
  timestamp: string
  open: number | null
  high: number | null
  low: number | null
  close: number
}

const COMMODITY_CATEGORIES: Record<string, string> = {
  crude_oil: 'energy',
  lng: 'energy',
  coal: 'energy',
  copper: 'metals',
  iron_ore: 'metals',
  aluminium: 'metals',
  nickel: 'metals',
  wheat: 'agriculture',
  soybeans: 'agriculture',
}

export const useCommodityStore = defineStore('commodity', () => {
  const prices = ref<CommodityPrice[]>([])
  const priceHistory = ref<PriceHistoryPoint[]>([])
  const selectedCommodity = ref<string | null>(null)
  const categoryFilter = ref<string | null>(null)
  const timeframe = ref<string>('1M')
  const loading = ref(false)

  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  async function getHeaders(): Promise<Record<string, string>> {
    const auth = useAuthStore()
    const token = await auth.getToken()
    return token
      ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' }
  }

  const filteredPrices = computed(() => {
    if (!categoryFilter.value) return prices.value
    return prices.value.filter(
      p => COMMODITY_CATEGORIES[p.commodity] === categoryFilter.value
    )
  })

  async function fetchPrices() {
    const headers = await getHeaders()
    try {
      const res = await fetch(`${apiBase}/api/v1/commodities/prices`, { headers })
      if (res.ok) {
        const body = await res.json()
        prices.value = body.data
      }
    } catch (e) {
      console.error('Failed to fetch commodity prices:', e)
    }
  }

  async function fetchPriceHistory(commodity: string) {
    loading.value = true
    const headers = await getHeaders()

    const intervalMap: Record<string, string> = {
      '1D': '1h', '1W': '4h', '1M': '1d', '3M': '1d', '1Y': '1w',
    }
    const daysMap: Record<string, number> = {
      '1D': 1, '1W': 7, '1M': 30, '3M': 90, '1Y': 365,
    }

    const interval = intervalMap[timeframe.value] || '1d'
    const days = daysMap[timeframe.value] || 30
    const from = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10)

    try {
      const res = await fetch(
        `${apiBase}/api/v1/commodities/prices/${commodity}/history?interval=${interval}&from=${from}`,
        { headers }
      )
      if (res.ok) {
        const body = await res.json()
        priceHistory.value = body.data
      }
    } catch (e) {
      console.error('Failed to fetch price history:', e)
    } finally {
      loading.value = false
    }
  }

  function selectCommodity(commodity: string) {
    selectedCommodity.value = commodity
    fetchPriceHistory(commodity)
  }

  return {
    prices,
    priceHistory,
    selectedCommodity,
    categoryFilter,
    timeframe,
    loading,
    filteredPrices,
    fetchPrices,
    fetchPriceHistory,
    selectCommodity,
  }
})
