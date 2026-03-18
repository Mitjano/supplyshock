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

    <!-- Supply Trends -->
    <div class="ss-card trends-section">
      <div class="trends-header">
        <h2>{{ t('analytics.trend.title') }}</h2>
        <span class="text-muted trends-subtitle">{{ t('analytics.trend.subtitle') }}</span>
      </div>

      <div v-if="trendLoading" class="trends-grid">
        <div v-for="i in 4" :key="i" class="trend-card skeleton-card">
          <div class="skeleton-line skeleton-title" />
          <div class="skeleton-line skeleton-bar" style="height: 120px" />
        </div>
      </div>

      <div v-else-if="trendData.length === 0" class="empty-state text-muted">
        {{ t('common.noData') }}
      </div>

      <div v-else class="trends-grid">
        <div v-for="trend in trendData" :key="trend.commodity" class="trend-card">
          <div class="trend-card-header">
            <span class="trend-commodity">{{ formatName(trend.commodity) }}</span>
            <span class="trend-badge" :class="'trend-' + trend.direction">
              <i :class="trendIcon(trend.direction)" />
              {{ t('analytics.trend.' + trend.direction) }}
            </span>
          </div>
          <div
            class="trend-chart-container"
            :ref="(el) => registerTrendChart(el as HTMLElement, trend.commodity)"
          />
        </div>
      </div>
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
const priceBands = ref<any>(null)
const flows = ref<any[]>([])
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
const sparklineInstances = new Map<string, echarts.ECharts>()
let pollInterval: ReturnType<typeof setInterval> | null = null

// Supply Trends state
interface TrendItem {
  commodity: string
  direction: 'growing' | 'declining' | 'stable'
  history: { date: string; volume: number }[]
  prediction: { date: string; volume: number }[]
}
const trendData = ref<TrendItem[]>([])
const trendLoading = ref(false)
const trendChartInstances = new Map<string, echarts.ECharts>()

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
    const [historyResp, bandsResp] = await Promise.all([
      apiFetch(
        `/commodities/prices/${selectedCommodity.value}/history`,
        { days: String(selectedDays.value) }
      ),
      apiFetch('/analytics/price-bands', { commodity: selectedCommodity.value }).catch(() => null),
    ])
    historyData.value = historyResp.data || []
    priceBands.value = bandsResp?.data || null
    await nextTick()
    renderChart()
  } catch {
    historyData.value = []
    priceBands.value = null
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

  // Build band data aligned to the history time axis
  const bands = priceBands.value?.bands || []
  const bandMap = new Map<string, any>()
  for (const b of bands) {
    bandMap.set(b.date, b)
  }

  // For each history time point, find the matching band entry (by date portion)
  const upper2 = times.map((t: string) => {
    const day = t.slice(0, 10)
    return bandMap.get(day)?.upper_2s ?? null
  })
  const lower2 = times.map((t: string) => {
    const day = t.slice(0, 10)
    return bandMap.get(day)?.lower_2s ?? null
  })
  const upper1 = times.map((t: string) => {
    const day = t.slice(0, 10)
    return bandMap.get(day)?.upper_1s ?? null
  })
  const lower1 = times.map((t: string) => {
    const day = t.slice(0, 10)
    return bandMap.get(day)?.lower_1s ?? null
  })
  const meanLine = times.map((t: string) => {
    const day = t.slice(0, 10)
    return bandMap.get(day)?.mean ?? null
  })

  const hasBands = bands.length > 0

  const series: any[] = []

  // 2σ band (darker shaded area) — rendered as two lines with area between
  if (hasBands) {
    series.push({
      name: '-2\u03c3',
      type: 'line',
      data: lower2,
      smooth: true,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      stack: 'band2',
      stackStrategy: 'all',
      silent: true,
    })
    series.push({
      name: '\u00b12\u03c3 band',
      type: 'line',
      data: upper2.map((u: number | null, i: number) =>
        u !== null && lower2[i] !== null ? u - lower2[i] : null
      ),
      smooth: true,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color: 'rgba(239,68,68,0.08)' },
      stack: 'band2',
      stackStrategy: 'all',
      silent: true,
    })
  }

  // 1σ band (lighter shaded area)
  if (hasBands) {
    series.push({
      name: '-1\u03c3',
      type: 'line',
      data: lower1,
      smooth: true,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      stack: 'band1',
      stackStrategy: 'all',
      silent: true,
    })
    series.push({
      name: '\u00b11\u03c3 band',
      type: 'line',
      data: upper1.map((u: number | null, i: number) =>
        u !== null && lower1[i] !== null ? u - lower1[i] : null
      ),
      smooth: true,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color: 'rgba(251,191,36,0.12)' },
      stack: 'band1',
      stackStrategy: 'all',
      silent: true,
    })
  }

  // Mean line
  if (hasBands) {
    series.push({
      name: 'Mean',
      type: 'line',
      data: meanLine,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' },
      silent: true,
    })
  }

  // Price line (on top)
  series.push({
    name: 'Price',
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
    z: 10,
  })

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const visible = params.filter((p: any) => p.value != null)
        if (visible.length === 0) return ''
        let html = `<strong>${visible[0].axisValueLabel}</strong><br/>`
        for (const p of visible) {
          if (p.seriesName.startsWith('-')) continue  // skip lower band base
          html += `${p.marker} ${p.seriesName}: ${typeof p.value === 'number' ? '$' + p.value.toFixed(2) : p.value}<br/>`
        }
        return html
      },
    },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: times, axisLabel: { formatter: (v: string) => v.slice(5, 10) } },
    yAxis: { type: 'value', scale: true },
    series,
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

// --- Supply Trends ---
function trendIcon(direction: string): string {
  if (direction === 'growing') return 'pi pi-arrow-up-right'
  if (direction === 'declining') return 'pi pi-arrow-down-right'
  return 'pi pi-minus'
}

async function fetchTrends() {
  trendLoading.value = true
  try {
    // Fetch trend for each displayed commodity (first 8)
    const commodities = filteredPrices.value.slice(0, 8).map(p => p.commodity)
    const results = await Promise.allSettled(
      commodities.map(async (commodity: string) => {
        const data = await apiFetch(`/commodities/flows/${commodity}/trend`, { days: '90' })
        return {
          commodity,
          direction: data.direction || 'stable',
          history: data.history || [],
          prediction: data.prediction || [],
        } as TrendItem
      })
    )
    trendData.value = results
      .filter((r): r is PromiseFulfilledResult<TrendItem> => r.status === 'fulfilled')
      .map(r => r.value)
  } catch {
    trendData.value = []
  } finally {
    trendLoading.value = false
  }
}

function registerTrendChart(el: HTMLElement | null, commodity: string) {
  if (!el || trendChartInstances.has(commodity)) return
  const trend = trendData.value.find(t => t.commodity === commodity)
  if (!trend) return

  const chart = echarts.init(el)
  trendChartInstances.set(commodity, chart)

  const historyDates = trend.history.map(d => d.date)
  const historyVols = trend.history.map(d => d.volume)
  const predDates = trend.prediction.map(d => d.date)
  const predVols = trend.prediction.map(d => d.volume)

  const allDates = [...historyDates, ...predDates]
  // For the prediction series, pad with nulls for history portion
  const predSeries = [...Array(historyDates.length).fill(null), ...predVols]
  // Connect the lines: last history value = first prediction value
  if (historyVols.length > 0 && predVols.length > 0) {
    predSeries[historyDates.length - 1] = historyVols[historyVols.length - 1]
  }
  const historySeries = [...historyVols, ...Array(predDates.length).fill(null)]

  chart.setOption({
    grid: { left: 40, right: 10, top: 10, bottom: 20 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: allDates,
      axisLabel: { formatter: (v: string) => v.slice(5, 10), fontSize: 10, color: '#64748b' },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { fontSize: 10, color: '#64748b' },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    series: [
      {
        name: 'Volume',
        type: 'line',
        data: historySeries,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59,130,246,0.2)' },
            { offset: 1, color: 'rgba(59,130,246,0)' },
          ]),
        },
      },
      {
        name: 'Prediction',
        type: 'line',
        data: predSeries,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#a78bfa', width: 2, type: 'dashed' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(167,139,250,0.1)' },
            { offset: 1, color: 'rgba(167,139,250,0)' },
          ]),
        },
      },
    ],
  })
}

// Refetch trends when prices load
watch(filteredPrices, (val) => {
  if (val.length > 0 && trendData.value.length === 0) {
    fetchTrends()
  }
})

onMounted(() => {
  fetchPrices()
  pollInterval = setInterval(fetchPrices, 60_000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (chartInstance) chartInstance.dispose()
  sparklineInstances.forEach(c => c.dispose())
  sparklineInstances.clear()
  trendChartInstances.forEach(c => c.dispose())
  trendChartInstances.clear()
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

/* Supply Trends */
.trends-section { padding: 1.5rem; margin-top: 1.5rem; }
.trends-header { margin-bottom: 1rem; }
.trends-header h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 0.25rem; }
.trends-subtitle { font-size: 0.8rem; }

.trends-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }

.trend-card {
  background: var(--bg-card, rgba(15,23,42,0.6));
  border: 1px solid var(--border-color, #2a2a3e);
  border-radius: 8px;
  padding: 0.75rem;
  transition: border-color 0.2s;
}
.trend-card:hover { border-color: var(--accent, #3b82f6); }

.trend-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}
.trend-commodity { font-weight: 600; font-size: 0.9rem; }

.trend-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.trend-growing { background: rgba(34,197,94,0.15); color: #4ade80; }
.trend-declining { background: rgba(239,68,68,0.15); color: #f87171; }
.trend-stable { background: rgba(148,163,184,0.15); color: #94a3b8; }

.trend-chart-container { height: 120px; }
</style>
