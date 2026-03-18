<template>
  <div class="view-container fade-in">
    <header class="view-header">
      <h1>{{ t('commodities.title') }}</h1>
    </header>

    <!-- Category filters -->
    <div class="category-tabs">
      <button
        v-for="cat in categories"
        :key="cat.key"
        class="tab-btn"
        :class="{ active: selectedCategory === cat.key }"
        @click="selectedCategory = cat.key"
      >
        {{ cat.label }}
      </button>
    </div>

    <!-- Price cards grid -->
    <div v-if="loading" class="cards-grid">
      <div v-for="i in 8" :key="i" class="ss-card price-card skeleton-card">
        <div class="skeleton-line skeleton-title" />
        <div class="skeleton-line skeleton-value" />
        <div class="skeleton-line skeleton-bar" />
      </div>
    </div>

    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchPrices">{{ t('common.retry') }}</button>
    </div>

    <div v-else class="cards-grid">
      <div
        v-for="item in filteredPrices"
        :key="item.commodity + item.benchmark"
        class="ss-card price-card"
        :class="{ selected: selectedCommodity === item.commodity }"
        @click="selectCommodity(item.commodity)"
      >
        <div class="price-header">
          <span class="commodity-name">{{ formatName(item.commodity) }}</span>
          <span class="commodity-benchmark text-muted">{{ item.benchmark }}</span>
        </div>
        <div class="price-value">
          ${{ item.price.toFixed(2) }}
          <span class="price-unit text-muted">/ {{ item.unit }}</span>
        </div>
        <div class="price-change" :class="item.change >= 0 ? 'text-success' : 'text-danger'">
          <i :class="item.change >= 0 ? 'pi pi-arrow-up' : 'pi pi-arrow-down'" />
          {{ Math.abs(item.change).toFixed(2) }}%
        </div>
        <div class="sparkline-container" :ref="(el) => registerSparkline(el as HTMLElement, item.commodity)" />
      </div>
    </div>

    <!-- History chart -->
    <div v-if="selectedCommodity" class="ss-card chart-card">
      <div class="chart-header">
        <h2>{{ formatName(selectedCommodity) }} — {{ t('commodities.price') }}</h2>
        <div class="timeframe-tabs">
          <button
            v-for="tf in timeframes"
            :key="tf.days"
            class="tab-btn tab-btn--sm"
            :class="{ active: selectedDays === tf.days }"
            @click="selectedDays = tf.days; fetchHistory()"
          >
            {{ tf.label }}
          </button>
        </div>
      </div>
      <div v-if="historyLoading" class="chart-placeholder skeleton-bar" style="height: 300px" />
      <div v-else ref="chartRef" class="price-chart" />
    </div>

    <!-- Trade flows -->
    <div v-if="selectedCommodity" class="ss-card flows-card">
      <h2>{{ t('commodities.tradeFlows') }}</h2>
      <div v-if="flows.length === 0" class="empty-state text-muted">
        {{ t('common.noData') }}
      </div>
      <table v-else class="ss-table">
        <thead>
          <tr>
            <th>{{ t('commodities.origin') }}</th>
            <th>{{ t('commodities.destination') }}</th>
            <th>{{ t('commodities.volumeMT') }}</th>
            <th>{{ t('commodities.valueUSD') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(flow, i) in flows" :key="i">
            <td>{{ flow.origin }}</td>
            <td>{{ flow.destination }}</td>
            <td>{{ flow.volume_mt ? Number(flow.volume_mt).toLocaleString() : '—' }}</td>
            <td>{{ flow.value_usd ? '$' + Number(flow.value_usd).toLocaleString() : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@clerk/vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// State
const loading = ref(true)
const error = ref(false)
const prices = ref<any[]>([])
const selectedCategory = ref('all')
const selectedCommodity = ref<string | null>(null)
const selectedDays = ref(30)
const historyLoading = ref(false)
const historyData = ref<any[]>([])
const flows = ref<any[]>([])
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
const sparklineInstances = new Map<string, echarts.ECharts>()
let pollInterval: ReturnType<typeof setInterval> | null = null

const categories = [
  { key: 'all', label: computed(() => t('commodities.all')) },
  { key: 'energy', label: computed(() => t('commodities.energy')) },
  { key: 'metals', label: computed(() => t('commodities.metals')) },
  { key: 'agriculture', label: computed(() => t('commodities.agriculture')) },
]

const timeframes = [
  { days: 7, label: '1W' },
  { days: 30, label: '1M' },
  { days: 90, label: '3M' },
  { days: 365, label: '1Y' },
]

const CATEGORY_MAP: Record<string, string[]> = {
  energy: ['crude_oil', 'lng', 'coal', 'brent', 'wti', 'natural_gas'],
  metals: ['iron_ore', 'copper', 'aluminium', 'nickel', 'gold', 'silver', 'zinc'],
  agriculture: ['wheat', 'soybeans', 'corn', 'rice', 'sugar', 'coffee', 'cotton'],
}

const filteredPrices = computed(() => {
  if (selectedCategory.value === 'all') return prices.value
  const allowed = CATEGORY_MAP[selectedCategory.value] || []
  return prices.value.filter(p => allowed.includes(p.commodity))
})

function formatName(commodity: string): string {
  return commodity
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

async function apiFetch(path: string, params?: Record<string, string>) {
  const token = await getToken.value()
  const url = new URL(`${API_BASE}/api/v1${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const resp = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) throw new Error(`${resp.status}`)
  return resp.json()
}

async function fetchPrices() {
  loading.value = true
  error.value = false
  try {
    const data = await apiFetch('/commodities/prices', { limit: '50' })
    // Add mock change % (will be real when we have 24h comparison)
    prices.value = (data.data || []).map((p: any) => ({
      ...p,
      change: (Math.random() - 0.45) * 5, // placeholder
    }))
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function selectCommodity(commodity: string) {
  selectedCommodity.value = selectedCommodity.value === commodity ? null : commodity
  if (selectedCommodity.value) {
    fetchHistory()
    fetchFlows()
  }
}

async function fetchHistory() {
  if (!selectedCommodity.value) return
  historyLoading.value = true
  try {
    const data = await apiFetch(
      `/commodities/prices/${selectedCommodity.value}/history`,
      { days: String(selectedDays.value) }
    )
    historyData.value = data.data || []
    await nextTick()
    renderChart()
  } catch {
    historyData.value = []
  } finally {
    historyLoading.value = false
  }
}

async function fetchFlows() {
  if (!selectedCommodity.value) return
  try {
    const data = await apiFetch('/commodities/flows', {
      commodity: selectedCommodity.value,
      limit: '10',
    })
    flows.value = (data.features || []).map((f: any) => f.properties)
  } catch {
    flows.value = []
  }
}

function renderChart() {
  if (!chartRef.value || historyData.value.length === 0) return

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const times = historyData.value.map(d => d.time)
  const vals = historyData.value.map(d => d.price)

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: times, axisLabel: { formatter: (v: string) => v.slice(5, 10) } },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'line',
      data: vals,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59,130,246,0.3)' },
          { offset: 1, color: 'rgba(59,130,246,0)' },
        ]),
      },
    }],
  })
}

function registerSparkline(el: HTMLElement | null, symbol: string) {
  if (!el || sparklineInstances.has(symbol)) return
  const chart = echarts.init(el)
  const data = Array.from({ length: 20 }, () => Math.random() * 10 + 50)
  chart.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { show: false, type: 'category' },
    yAxis: { show: false, type: 'value', scale: true },
    series: [{ type: 'line', data, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#3b82f6' } }],
  })
  sparklineInstances.set(symbol, chart)
}

onMounted(() => {
  fetchPrices()
  pollInterval = setInterval(fetchPrices, 60_000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (chartInstance) chartInstance.dispose()
  sparklineInstances.forEach(c => c.dispose())
  sparklineInstances.clear()
})
</script>

<style scoped>
.view-header { margin-bottom: 1.5rem; }
.view-header h1 { font-size: 1.5rem; font-weight: 700; }

.category-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.tab-btn {
  padding: 0.5rem 1rem; border-radius: 8px; border: 1px solid var(--border-color, #2a2a3e);
  background: transparent; color: var(--text-secondary, #94a3b8); cursor: pointer;
  font-size: 0.85rem; transition: all 0.2s;
}
.tab-btn:hover { background: var(--bg-hover, rgba(255,255,255,0.05)); }
.tab-btn.active { background: var(--accent, #3b82f6); color: white; border-color: transparent; }
.tab-btn--sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; }

.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }

.price-card {
  padding: 1rem; cursor: pointer; transition: all 0.2s;
  border: 1px solid var(--border-color, #2a2a3e);
}
.price-card:hover { border-color: var(--accent, #3b82f6); }
.price-card.selected { border-color: var(--accent, #3b82f6); background: var(--bg-hover, rgba(59,130,246,0.08)); }

.price-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.commodity-name { font-weight: 600; font-size: 0.95rem; }
.commodity-benchmark { font-size: 0.75rem; }
.price-value { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.25rem; }
.price-unit { font-size: 0.75rem; font-weight: 400; }
.price-change { font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; }

.sparkline-container { height: 40px; }

.chart-card { padding: 1.5rem; margin-bottom: 1.5rem; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
.chart-header h2 { font-size: 1.1rem; font-weight: 600; }
.timeframe-tabs { display: flex; gap: 0.25rem; }
.price-chart { height: 300px; }

.flows-card { padding: 1.5rem; }
.flows-card h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }

.error-state { text-align: center; padding: 3rem; color: var(--text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }

.skeleton-card { animation: pulse 1.5s ease-in-out infinite; }
.skeleton-title { height: 1rem; width: 60%; background: var(--bg-hover, #2a2a3e); border-radius: 4px; margin-bottom: 0.5rem; }
.skeleton-value { height: 1.5rem; width: 40%; background: var(--bg-hover, #2a2a3e); border-radius: 4px; margin-bottom: 0.5rem; }
.skeleton-bar { height: 40px; background: var(--bg-hover, #2a2a3e); border-radius: 4px; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
