<template>
  <div class="commodity-dashboard">
    <header class="dashboard-header">
      <h1>Commodity Prices</h1>
      <div class="category-filters">
        <button
          v-for="cat in categories"
          :key="cat.value"
          :class="['filter-btn', { active: store.categoryFilter === cat.value }]"
          @click="store.categoryFilter = store.categoryFilter === cat.value ? null : cat.value"
        >
          {{ cat.label }}
        </button>
      </div>
    </header>

    <section class="price-grid">
      <div
        v-for="p in store.filteredPrices"
        :key="p.commodity + p.benchmark"
        :class="['price-card', { selected: store.selectedCommodity === p.commodity }]"
        @click="store.selectCommodity(p.commodity)"
      >
        <div class="card-header">
          <span class="commodity-name">{{ formatName(p.commodity) }}</span>
          <span class="benchmark">{{ p.benchmark }}</span>
        </div>
        <div class="card-price">${{ formatPrice(p.price) }}</div>
        <div class="card-unit">{{ p.unit }}</div>
        <div
          v-if="p.change_24h !== null"
          :class="['card-change', p.change_24h >= 0 ? 'positive' : 'negative']"
        >
          {{ p.change_24h >= 0 ? '+' : '' }}{{ p.change_24h.toFixed(2) }}%
        </div>
      </div>
    </section>

    <section v-if="store.selectedCommodity" class="chart-section">
      <div class="chart-header">
        <h2>{{ formatName(store.selectedCommodity) }} — Price History</h2>
        <div class="timeframe-btns">
          <button
            v-for="tf in timeframes"
            :key="tf"
            :class="['tf-btn', { active: store.timeframe === tf }]"
            @click="store.timeframe = tf; store.fetchPriceHistory(store.selectedCommodity!)"
          >
            {{ tf }}
          </button>
        </div>
      </div>

      <div v-if="store.loading" class="chart-loading">Loading chart data...</div>
      <div v-else-if="store.priceHistory.length" class="chart-container">
        <div class="simple-chart">
          <svg viewBox="0 0 800 300" preserveAspectRatio="none" class="sparkline-svg">
            <polyline
              :points="chartPoints"
              fill="none"
              stroke="#3b82f6"
              stroke-width="2"
            />
            <polygon
              :points="areaPoints"
              fill="url(#gradient)"
              opacity="0.15"
            />
            <defs>
              <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#3b82f6" />
                <stop offset="100%" stop-color="#3b82f6" stop-opacity="0" />
              </linearGradient>
            </defs>
          </svg>
          <div class="chart-labels">
            <span>${{ minPrice.toFixed(2) }}</span>
            <span>${{ maxPrice.toFixed(2) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="chart-empty">No historical data available</div>
    </section>

    <section class="flows-section">
      <h2>Top Trade Flows</h2>
      <table class="flows-table">
        <thead>
          <tr>
            <th>Route</th>
            <th>Commodity</th>
            <th>Volume (MT)</th>
            <th>Value (USD)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="flow in topFlows" :key="flow.origin + flow.destination">
            <td>{{ flow.origin }} → {{ flow.destination }}</td>
            <td>{{ formatName(flow.commodity) }}</td>
            <td>{{ flow.volume_mt ? formatVolume(flow.volume_mt) : '—' }}</td>
            <td>{{ flow.value_usd ? formatUsd(flow.value_usd) : '—' }}</td>
          </tr>
          <tr v-if="!topFlows.length">
            <td colspan="4" class="empty-row">No trade flow data available</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from 'vue'
import { useCommodityStore } from '../stores/useCommodityStore'
import { useMapStore } from '../stores/useMapStore'

const store = useCommodityStore()
const mapStore = useMapStore()

const categories = [
  { label: 'All', value: null as string | null },
  { label: 'Energy', value: 'energy' },
  { label: 'Metals', value: 'metals' },
  { label: 'Agriculture', value: 'agriculture' },
]

const timeframes = ['1D', '1W', '1M', '3M', '1Y']

const topFlows = computed(() => {
  return mapStore.tradeFlows
    .map(f => f.properties)
    .filter(f => !store.categoryFilter || getCat(f.commodity) === store.categoryFilter)
    .sort((a, b) => (b.volume_mt || 0) - (a.volume_mt || 0))
    .slice(0, 10)
})

function getCat(commodity: string): string {
  const map: Record<string, string> = {
    crude_oil: 'energy', lng: 'energy', coal: 'energy',
    copper: 'metals', iron_ore: 'metals', aluminium: 'metals', nickel: 'metals',
    wheat: 'agriculture', soybeans: 'agriculture',
  }
  return map[commodity] || 'other'
}

const minPrice = computed(() => {
  if (!store.priceHistory.length) return 0
  return Math.min(...store.priceHistory.map(p => p.close))
})

const maxPrice = computed(() => {
  if (!store.priceHistory.length) return 0
  return Math.max(...store.priceHistory.map(p => p.close))
})

const chartPoints = computed(() => {
  const data = store.priceHistory
  if (!data.length) return ''
  const range = maxPrice.value - minPrice.value || 1
  return data
    .map((p, i) => {
      const x = (i / (data.length - 1)) * 800
      const y = 300 - ((p.close - minPrice.value) / range) * 280 - 10
      return `${x},${y}`
    })
    .join(' ')
})

const areaPoints = computed(() => {
  if (!chartPoints.value) return ''
  const data = store.priceHistory
  const lastX = (data.length - 1) / (data.length - 1) * 800
  return `0,300 ${chartPoints.value} ${lastX},300`
})

function formatName(commodity: string): string {
  return commodity.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatPrice(price: number): string {
  return price >= 1000 ? price.toLocaleString('en-US', { maximumFractionDigits: 0 })
    : price.toFixed(2)
}

function formatVolume(mt: number): string {
  if (mt >= 1e9) return (mt / 1e9).toFixed(1) + 'B'
  if (mt >= 1e6) return (mt / 1e6).toFixed(1) + 'M'
  if (mt >= 1e3) return (mt / 1e3).toFixed(0) + 'K'
  return mt.toString()
}

function formatUsd(usd: number): string {
  if (usd >= 1e9) return '$' + (usd / 1e9).toFixed(1) + 'B'
  if (usd >= 1e6) return '$' + (usd / 1e6).toFixed(1) + 'M'
  return '$' + usd.toLocaleString()
}

let refreshInterval: ReturnType<typeof setInterval>

onMounted(() => {
  store.fetchPrices()
  mapStore.fetchTradeFlows()
  refreshInterval = setInterval(() => store.fetchPrices(), 60000)
})

onUnmounted(() => {
  clearInterval(refreshInterval)
})
</script>

<style scoped>
.commodity-dashboard {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  color: #f1f5f9;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.dashboard-header h1 {
  font-size: 1.75rem;
  margin: 0;
}

.category-filters {
  display: flex;
  gap: 0.5rem;
}

.filter-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.filter-btn.active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
}

.price-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.price-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.price-card:hover {
  border-color: #3b82f6;
}

.price-card.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.commodity-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.benchmark {
  color: #64748b;
  font-size: 0.75rem;
}

.card-price {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.card-unit {
  color: #64748b;
  font-size: 0.8rem;
  margin-bottom: 0.5rem;
}

.card-change {
  font-size: 0.9rem;
  font-weight: 600;
}

.card-change.positive { color: #10b981; }
.card-change.negative { color: #ef4444; }

.chart-section {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.chart-header h2 {
  font-size: 1.1rem;
  margin: 0;
}

.timeframe-btns {
  display: flex;
  gap: 0.25rem;
}

.tf-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
}

.tf-btn.active {
  background: #334155;
  color: #f1f5f9;
}

.chart-container {
  height: 300px;
}

.simple-chart {
  position: relative;
  height: 100%;
}

.sparkline-svg {
  width: 100%;
  height: 100%;
}

.chart-labels {
  display: flex;
  justify-content: space-between;
  color: #64748b;
  font-size: 0.75rem;
  padding-top: 0.5rem;
}

.chart-loading, .chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #64748b;
}

.flows-section h2 {
  font-size: 1.25rem;
  margin-bottom: 1rem;
}

.flows-table {
  width: 100%;
  border-collapse: collapse;
  background: #1e293b;
  border-radius: 12px;
  overflow: hidden;
}

.flows-table th {
  background: #0f172a;
  text-align: left;
  padding: 0.75rem 1rem;
  color: #64748b;
  font-size: 0.8rem;
  text-transform: uppercase;
  font-weight: 600;
}

.flows-table td {
  padding: 0.75rem 1rem;
  border-top: 1px solid #1e293b;
  color: #cbd5e1;
  font-size: 0.9rem;
}

.flows-table tr:hover td {
  background: #334155;
}

.empty-row {
  text-align: center;
  color: #64748b;
}
</style>
