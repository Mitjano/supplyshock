import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '@/composables/useApi'

export interface WatchlistItem {
  commodity: string
  price: number | null
  unit: string | null
  change_24h: number | null
  benchmark: string | null
  price_time: string | null
  sparkline_7d: number[]
}

export const useWatchlistStore = defineStore('watchlist', () => {
  const api = useApi()
  const items = ref<WatchlistItem[]>([])
  const loading = ref(false)

  const commoditySet = computed(() => new Set(items.value.map(i => i.commodity)))

  function isWatched(commodity: string): boolean {
    return commoditySet.value.has(commodity)
  }

  async function fetchWatchlist() {
    loading.value = true
    try {
      const res = await api.get<{ data: WatchlistItem[] }>('/watchlist')
      items.value = res.data
    } catch (e) {
      console.error('Failed to fetch watchlist:', e)
    } finally {
      loading.value = false
    }
  }

  async function addCommodity(commodity: string) {
    try {
      await api.post('/watchlist', { commodity })
      await fetchWatchlist()
    } catch (e) {
      console.error('Failed to add to watchlist:', e)
    }
  }

  async function removeCommodity(commodity: string) {
    try {
      await api.del(`/watchlist/${commodity}`)
      items.value = items.value.filter(i => i.commodity !== commodity)
    } catch (e) {
      console.error('Failed to remove from watchlist:', e)
    }
  }

  async function toggleCommodity(commodity: string) {
    if (isWatched(commodity)) {
      await removeCommodity(commodity)
    } else {
      await addCommodity(commodity)
    }
  }

  return {
    items,
    loading,
    commoditySet,
    isWatched,
    fetchWatchlist,
    addCommodity,
    removeCommodity,
    toggleCommodity,
  }
})
