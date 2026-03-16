<template>
  <div class="commodity-dashboard">
    <!-- Header -->
    <header class="cd-header">
      <div class="cd-header__left">
        <h1>{{ t('commodities.title') }}</h1>
        <span class="cd-header__live-dot" />
        <span class="cd-header__live-label">LIVE</span>
      </div>
      <SelectButton
        v-model="store.categoryFilter"
        :options="categories"
        optionLabel="label"
        optionValue="value"
        :allowEmpty="true"
        class="cd-category-filter"
      />
    </header>

    <!-- Price Cards Grid -->
    <section class="cd-price-grid">
      <template v-if="pricesLoading">
        <div v-for="i in 8" :key="i" class="cd-price-card cd-price-card--skeleton">
          <Skeleton width="60%" height="0.875rem" class="mb-2" />
          <Skeleton width="40%" height="1.75rem" class="mb-1" />
          <Skeleton width="30%" height="0.75rem" class="mb-2" />
          <Skeleton width="100%" height="50px" />
        </div>
      </template>

      <template v-else-if="pricesError">
        <div class="cd-error-state">
          <i class="pi pi-exclamation-triangle" />
          <p>{{ t('common.error') }}</p>
          <button class="cd-btn cd-btn--primary" @click="loadPrices">
            {{ t('common.retry') }}
          </button>
        </div>
      </template>

      <template v-else>
        <div
          v-for="p in store.filteredPrices"
          :key="p.commodity + p.benchmark"
          :class="['cd-price-card', { 'cd-price-card--selected': store.selectedCommodity === p.commodity }]"
          @click="selectCommodity(p.commodity)"
        >
          <div class="cd-price-card__head">
            <span class="cd-price-card__icon">{{ commodityIcon(p.commodity) }}</span>
            <span class="cd-price-card__name">{{ formatName(p.commodity) }}</span>
            <span class="cd-price-card__benchmark">{{ p.benchmark }}</span>
          </div>
          <div class="cd-price-card__price">${{ formatPrice(p.price) }}</div>
          <div class="cd-price-card__meta">
            <span
              v-if="p.change_24h !== null"
              :class="['cd-price-card__change', p.change_24h >= 0 ? 'cd-up' : 'cd-down']"
            >
              <i :class="p.change_24h >= 0 ? 'pi pi-arrow-up-right' : 'pi pi-arrow-down-right'" />
              {{ p.change_24h >= 0 ? '+' : '' }}{{ p.change_24h.toFixed(2) }}%
            </span>
            <span class="cd-price-card__unit">{{ p.unit }}</span>
          </div>
          <div class="cd-price-card__spark" :ref="(el) => setSparkRef(p.commodity, el as HTMLElement)" />
        </div>
      </template>
    </section>

    <!-- Main Chart Area -->
    <section v-if="store.selectedCommodity" class="cd-chart-section fade-in">
      <div class="cd-chart-header">
        <div class="cd-chart-header__left">
          <span class="cd-chart-header__icon">{{ commodityIcon(store.selectedCommodity) }}</span>
          <h2>{{ formatName(store.selectedCommodity) }}</h2>
          <span v-if="selectedPrice" class="cd-chart-header__price">
            ${{ formatPrice(selectedPrice.price) }}
          </span>
          <span
            v-if="selectedPrice?.change_24h !== null && selectedPrice?.change_24h !== undefined"
            :class="['cd-chart-header__change', (selectedPrice?.change_24h ?? 0) >= 0 ? 'cd-up' : 'cd-down']"
          >
            {{ (selectedPrice?.change_24h ?? 0) >= 0 ? '+' : '' }}{{ selectedPrice?.change_24h?.toFixed(2) }}%
          </span>
        </div>
        <div class="cd-chart-header__right">
          <SelectButton
            v-model="store.timeframe"
            :options="timeframeOptions"
            optionLabel="label"
            optionValue="value"
            class="cd-timeframe-select"
            @change="onTimeframeChange"
          />
        </div>
      </div>

      <div v-if="store.loading" class="cd-chart-loading">
        <Skeleton width="100%" height="400px" />
      </div>
      <div v-else-if="chartError" class="cd-chart-error">
        <i class="pi pi-exclamation-triangle" />
        <p>{{ t('commodities.chartError') }}</p>
        <button class="cd-btn cd-btn--primary" @click="retryChart">
          {{ t('common.retry') }}
        </button>
      </div>
      <div v-else-if="store.priceHistory.length" class="cd-chart-container" ref="mainChartRef" />
      <div v-else class="cd-chart-empty">
        <i class="pi pi-chart-line" />
        <p>{{ t('common.noData') }}</p>
      </div>
    </section>

    <!-- Empty state when no commodity selected -->
    <section v-else class="cd-chart-placeholder fade-in">
      <i class="pi pi-chart-line" />
      <p>{{ t('commodities.selectCommodity') }}</p>
    </section>

    <!-- Trade Flows Table -->
    <section class="cd-flows-section">
      <div class="cd-flows-header">
        <h2>{{ t('commodities.tradeFlows') }}</h2>
        <span class="cd-flows-count" v-if="sortedFlows.length">
          {{ sortedFlows.length }} {{ t('commodities.routes') }}
        </span>
      </div>

      <div class="cd-flows-table-wrap">
        <table class="cd-flows-table">
          <thead>
            <tr>
              <th @click="toggleSort('route')" class="cd-flows-th--sortable">
                {{ t('commodities.origin') }} / {{ t('commodities.destination') }}
                <i :class="sortIcon('route')" />
              </th>
              <th @click="toggleSort('commodity')" class="cd-flows-th--sortable">
                {{ t('commodities.commodity') }}
                <i :class="sortIcon('commodity')" />
              </th>
              <th @click="toggleSort('volume')" class="cd-flows-th--sortable cd-flows-th--right">
                {{ t('commodities.volumeMT') }}
                <i :class="sortIcon('volume')" />
              </th>
              <th @click="toggleSort('value')" class="cd-flows-th--sortable cd-flows-th--right">
                {{ t('commodities.valueUSD') }}
                <i :class="sortIcon('value')" />
              </th>
              <th>{{ t('commodities.period') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="flow in sortedFlows" :key="flow.origin + flow.destination + flow.commodity">
              <td>
                <span class="cd-flow-route">
                  <span class="cd-flow-origin">{{ flow.origin }}</span>
                  <i class="pi pi-arrow-right cd-flow-arrow" />
                  <span class="cd-flow-dest">{{ flow.destination }}</span>
                </span>
              </td>
              <td>
                <span class="cd-flow-commodity">
                  {{ commodityIcon(flow.commodity) }} {{ formatName(flow.commodity) }}
                </span>
              </td>
              <td class="cd-flows-td--right">{{ flow.volume_mt ? formatVolume(flow.volume_mt) : '--' }}</td>
              <td class="cd-flows-td--right">{{ flow.value_usd ? formatUsd(flow.value_usd) : '--' }}</td>
              <td class="cd-flows-td--muted">{{ t('commodities.periodLatest') }}</td>
            </tr>
            <tr v-if="!sortedFlows.length">
              <td colspan="5" class="cd-flows-empty">{{ t('common.noData') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import SelectButton from 'primevue/selectbutton'
import Skeleton from 'primevue/skeleton'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import { useCommodityStore } from '../stores/useCommodityStore'
import { useMapStore } from '../stores/useMapStore'
import { useChart } from '../composables/useChart'

echarts.use([LineChart, TooltipComponent, GridComponent, DataZoomComponent, CanvasRenderer])

const { t } = useI18n()
const store = useCommodityStore()
const mapStore = useMapStore()

// ---- State ----
const pricesLoading = ref(true)
const pricesError = ref(false)
const chartError = ref(false)
const mainChartRef = ref<HTMLElement | null>(null)
const { chart: mainChart, setOption: setMainOption } = useChart(mainChartRef)

// Sparkline chart instances
const sparkRefs = new Map<string, HTMLElement>()
const sparkCharts = new Map<string, echarts.ECharts>()

const sortColumn = ref<string>('volume')
const sortAsc = ref(false)

// ---- Constants ----
const categories = [
  { label: t('commodities.all'), value: null as string | null },
  { label: t('commodities.energy'), value: 'energy' },
  { label: t('commodities.metals'), value: 'metals' },
  { label: t('commodities.agriculture'), value: 'agriculture' },
  { label: t('commodities.carbon'), value: 'carbon' },
]

const timeframeOptions = [
  { label: '1D', value: '1D' },
  { label: '1W', value: '1W' },
  { label: '1M', value: '1M' },
  { label: '3M', value: '3M' },
  { label: '1Y', value: '1Y' },
]

const COMMODITY_ICONS: Record<string, string> = {
  crude_oil: '\u{1F6E2}',
  lng: '\u{1F525}',
  coal: '\u{26AB}',
  copper: '\u{1FA99}',
  iron_ore: '\u{1F9F2}',
  aluminium: '\u{1FAA8}',
  nickel: '\u{26AA}',
  wheat: '\u{1F33E}',
  soybeans: '\u{1F331}',
  carbon: '\u{1F30D}',
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

// ---- Computed ----
const selectedPrice = computed(() =>
  store.prices.find(p => p.commodity === store.selectedCommodity) ?? null
)

interface FlowRow {
  origin: string
  destination: string
  commodity: string
  volume_mt: number | null
  value_usd: number | null
}

const filteredFlows = computed<FlowRow[]>(() => {
  return mapStore.tradeFlows
    .map(f => f.properties)
    .filter(f => !store.categoryFilter || COMMODITY_CATEGORIES[f.commodity] === store.categoryFilter)
    .slice(0, 20)
})

const sortedFlows = computed(() => {
  const data = [...filteredFlows.value]
  const dir = sortAsc.value ? 1 : -1

  data.sort((a, b) => {
    switch (sortColumn.value) {
      case 'route':
        return dir * a.origin.localeCompare(b.origin)
      case 'commodity':
        return dir * a.commodity.localeCompare(b.commodity)
      case 'volume':
        return dir * ((a.volume_mt || 0) - (b.volume_mt || 0))
      case 'value':
        return dir * ((a.value_usd || 0) - (b.value_usd || 0))
      default:
        return 0
    }
  })
  return data
})

// ---- Methods ----
function commodityIcon(commodity: string): string {
  return COMMODITY_ICONS[commodity] || '\u{1F4E6}'
}

function formatName(commodity: string): string {
  return commodity.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatPrice(price: number): string {
  return price >= 1000
    ? price.toLocaleString('en-US', { maximumFractionDigits: 0 })
    : price.toFixed(2)
}

function formatVolume(mt: number): string {
  if (mt >= 1e9) return (mt / 1e9).toFixed(1) + 'B'
  if (mt >= 1e6) return (mt / 1e6).toFixed(1) + 'M'
  if (mt >= 1e3) return (mt / 1e3).toFixed(0) + 'K'
  return mt.toLocaleString()
}

function formatUsd(usd: number): string {
  if (usd >= 1e9) return '$' + (usd / 1e9).toFixed(1) + 'B'
  if (usd >= 1e6) return '$' + (usd / 1e6).toFixed(1) + 'M'
  return '$' + usd.toLocaleString()
}

function toggleSort(col: string) {
  if (sortColumn.value === col) {
    sortAsc.value = !sortAsc.value
  } else {
    sortColumn.value = col
    sortAsc.value = false
  }
}

function sortIcon(col: string): string {
  if (sortColumn.value !== col) return 'pi pi-sort-alt'
  return sortAsc.value ? 'pi pi-sort-amount-up-alt' : 'pi pi-sort-amount-down'
}

function setSparkRef(commodity: string, el: HTMLElement | null) {
  if (el) {
    sparkRefs.set(commodity, el)
  }
}

function selectCommodity(commodity: string) {
  chartError.value = false
  store.selectCommodity(commodity)
}

function onTimeframeChange() {
  if (store.selectedCommodity) {
    chartError.value = false
    store.fetchPriceHistory(store.selectedCommodity)
  }
}

function retryChart() {
  if (store.selectedCommodity) {
    chartError.value = false
    store.fetchPriceHistory(store.selectedCommodity)
  }
}

async function loadPrices() {
  pricesLoading.value = true
  pricesError.value = false
  try {
    await store.fetchPrices()
  } catch {
    pricesError.value = true
  } finally {
    pricesLoading.value = false
  }
}

// ---- Sparkline rendering ----
function renderSparkline(commodity: string, el: HTMLElement) {
  const history = store.priceHistory
  // For sparklines, we generate a simple synthetic dataset from current price
  // In production this would come from individual commodity mini-histories
  const existing = sparkCharts.get(commodity)
  if (existing) existing.dispose()

  const chart = echarts.init(el, undefined, { renderer: 'canvas' })
  sparkCharts.set(commodity, chart)

  const priceData = store.prices.find(p => p.commodity === commodity)
  if (!priceData) return

  // Generate a simple sparkline from change_24h for visual hint
  const basePrice = priceData.price
  const change = priceData.change_24h || 0
  const points = 20
  const data: number[] = []
  for (let i = 0; i < points; i++) {
    const progress = i / (points - 1)
    const startPrice = basePrice / (1 + change / 100)
    const noise = (Math.random() - 0.5) * basePrice * 0.005
    data.push(startPrice + (basePrice - startPrice) * progress + noise)
  }

  const color = change >= 0 ? '#22c55e' : '#ef4444'
  chart.setOption({
    grid: { top: 2, right: 0, bottom: 2, left: 0 },
    xAxis: { type: 'category', show: false, data: data.map((_, i) => i) },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [{
      type: 'line',
      data,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, color },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color + '30' },
          { offset: 1, color: color + '05' },
        ]),
      },
    }],
    animation: false,
  })
}

function renderAllSparklines() {
  nextTick(() => {
    for (const [commodity, el] of sparkRefs) {
      renderSparkline(commodity, el)
    }
  })
}

// ---- Main chart rendering ----
function renderMainChart() {
  if (!store.priceHistory.length || !mainChartRef.value) return

  const dates = store.priceHistory.map(p => {
    const d = new Date(p.timestamp)
    return store.timeframe === '1D'
      ? d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
      : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  })
  const closes = store.priceHistory.map(p => p.close)
  const highs = store.priceHistory.map(p => p.high ?? p.close)
  const lows = store.priceHistory.map(p => p.low ?? p.close)

  const lastClose = closes[closes.length - 1]
  const firstClose = closes[0]
  const trendColor = lastClose >= firstClose ? '#22c55e' : '#ef4444'

  setMainOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter(params: any) {
        const p = Array.isArray(params) ? params[0] : params
        const idx = p.dataIndex
        const high = highs[idx]
        const low = lows[idx]
        const close = closes[idx]
        return `
          <div style="font-weight:600;margin-bottom:4px">${dates[idx]}</div>
          <div>Close: <b>$${formatPrice(close)}</b></div>
          <div>High: $${formatPrice(high)}</div>
          <div>Low: $${formatPrice(low)}</div>
        `
      },
    },
    grid: {
      top: 20,
      right: 60,
      bottom: 60,
      left: 60,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#334155' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#64748b',
        fontSize: 11,
        rotate: dates.length > 60 ? 45 : 0,
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      position: 'right',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#64748b',
        fontSize: 11,
        formatter: (v: number) => '$' + formatPrice(v),
      },
      splitLine: {
        lineStyle: { color: '#1e293b', type: 'dashed' },
      },
    },
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 24,
        bottom: 8,
        borderColor: '#334155',
        backgroundColor: '#0f172a',
        fillerColor: 'rgba(59, 130, 246, 0.12)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#64748b', fontSize: 10 },
        dataBackground: {
          lineStyle: { color: '#334155' },
          areaStyle: { color: '#1e293b' },
        },
      },
    ],
    series: [
      {
        name: 'Price',
        type: 'line',
        data: closes,
        smooth: 0.3,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: trendColor,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: trendColor + '25' },
            { offset: 0.7, color: trendColor + '08' },
            { offset: 1, color: 'transparent' },
          ]),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#3b82f6', type: 'dashed', width: 1 },
          data: [
            { yAxis: lastClose, label: { formatter: '$' + formatPrice(lastClose), color: '#3b82f6', fontSize: 10 } },
          ],
        },
      },
    ],
  })
}

// ---- Watchers ----
watch(() => store.priceHistory, () => {
  nextTick(renderMainChart)
}, { deep: true })

watch(mainChartRef, (el) => {
  if (el) nextTick(renderMainChart)
})

watch(() => store.filteredPrices, () => {
  nextTick(renderAllSparklines)
}, { deep: true })

// ---- Lifecycle ----
let refreshInterval: ReturnType<typeof setInterval>

onMounted(async () => {
  await Promise.all([
    loadPrices(),
    mapStore.fetchTradeFlows(),
  ])
  nextTick(renderAllSparklines)
  refreshInterval = setInterval(async () => {
    await store.fetchPrices()
    renderAllSparklines()
  }, 60000)
})

onUnmounted(() => {
  clearInterval(refreshInterval)
  for (const chart of sparkCharts.values()) {
    chart.dispose()
  }
  sparkCharts.clear()
})
</script>

<style scoped>
.commodity-dashboard {
  padding: 1.5rem;
  max-width: 1440px;
  margin: 0 auto;
  color: var(--ss-text-primary);
}

/* ---- Header ---- */
.cd-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.cd-header__left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.cd-header__left h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.025em;
}

.cd-header__live-dot {
  width: 8px;
  height: 8px;
  background: var(--ss-success);
  border-radius: 50%;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5); }
  50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
}

.cd-header__live-label {
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--ss-success);
  text-transform: uppercase;
}

:deep(.cd-category-filter) {
  .p-selectbutton {
    gap: 2px;
    background: var(--ss-bg-surface);
    border: 1px solid var(--ss-border-light);
    border-radius: var(--ss-radius);
    padding: 3px;
  }
  .p-selectbutton .p-button {
    background: transparent;
    border: none;
    color: var(--ss-text-secondary);
    font-size: 0.8125rem;
    font-weight: 500;
    padding: 0.375rem 0.875rem;
    border-radius: var(--ss-radius-sm);
    transition: all var(--ss-transition-fast);
  }
  .p-selectbutton .p-button.p-highlight,
  .p-selectbutton .p-button[aria-pressed="true"] {
    background: var(--ss-info);
    color: #fff;
  }
  .p-selectbutton .p-button:hover:not(.p-highlight):not([aria-pressed="true"]) {
    background: var(--ss-bg-elevated);
    color: var(--ss-text-primary);
  }
}

/* ---- Price Cards Grid ---- */
.cd-price-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 1100px) {
  .cd-price-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 768px) {
  .cd-price-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 480px) {
  .cd-price-grid { grid-template-columns: 1fr; }
}

.cd-price-card {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1rem 1.125rem;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
  position: relative;
  overflow: hidden;
}

.cd-price-card:hover {
  border-color: var(--ss-info);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.cd-price-card--selected {
  border-color: var(--ss-info);
  box-shadow: 0 0 0 1px var(--ss-info), 0 4px 16px rgba(59, 130, 246, 0.15);
}

.cd-price-card--skeleton {
  padding: 1rem 1.125rem;
  cursor: default;
}

.cd-price-card--skeleton:hover {
  transform: none;
  box-shadow: none;
}

.cd-price-card__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.cd-price-card__icon {
  font-size: 1.125rem;
  line-height: 1;
}

.cd-price-card__name {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--ss-text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cd-price-card__benchmark {
  color: var(--ss-text-muted);
  font-size: 0.6875rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.cd-price-card__price {
  font-size: 1.375rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ss-text-primary);
  margin-bottom: 0.25rem;
  font-variant-numeric: tabular-nums;
}

.cd-price-card__meta {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 0.5rem;
}

.cd-price-card__change {
  font-size: 0.8125rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-variant-numeric: tabular-nums;
}

.cd-price-card__change i {
  font-size: 0.625rem;
}

.cd-up { color: var(--ss-success); }
.cd-down { color: var(--ss-danger); }

.cd-price-card__unit {
  color: var(--ss-text-muted);
  font-size: 0.75rem;
}

.cd-price-card__spark {
  width: 100%;
  height: 50px;
}

/* ---- Error State ---- */
.cd-error-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  gap: 0.75rem;
  color: var(--ss-text-muted);
}

.cd-error-state i {
  font-size: 2rem;
  color: var(--ss-warning);
}

/* ---- Buttons ---- */
.cd-btn {
  border: none;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.8125rem;
  border-radius: var(--ss-radius);
  padding: 0.5rem 1.25rem;
  transition: all var(--ss-transition-fast);
}

.cd-btn--primary {
  background: var(--ss-info);
  color: #fff;
}

.cd-btn--primary:hover {
  background: #2563eb;
}

/* ---- Chart Section ---- */
.cd-chart-section {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}

.cd-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.cd-chart-header__left {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.cd-chart-header__icon {
  font-size: 1.25rem;
}

.cd-chart-header__left h2 {
  font-size: 1.125rem;
  font-weight: 700;
  margin: 0;
}

.cd-chart-header__price {
  font-size: 1.125rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ss-text-primary);
  margin-left: 0.25rem;
}

.cd-chart-header__change {
  font-size: 0.875rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

:deep(.cd-timeframe-select) {
  .p-selectbutton {
    gap: 1px;
    background: var(--ss-bg-base);
    border: 1px solid var(--ss-border-light);
    border-radius: var(--ss-radius-sm);
    padding: 2px;
  }
  .p-selectbutton .p-button {
    background: transparent;
    border: none;
    color: var(--ss-text-muted);
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.3rem 0.625rem;
    border-radius: 4px;
    min-width: 2.5rem;
    transition: all var(--ss-transition-fast);
  }
  .p-selectbutton .p-button.p-highlight,
  .p-selectbutton .p-button[aria-pressed="true"] {
    background: var(--ss-bg-elevated);
    color: var(--ss-text-primary);
  }
}

.cd-chart-container {
  width: 100%;
  height: 400px;
}

.cd-chart-loading,
.cd-chart-empty,
.cd-chart-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: 0.75rem;
  color: var(--ss-text-muted);
}

.cd-chart-empty i,
.cd-chart-error i {
  font-size: 2.5rem;
  opacity: 0.3;
}

.cd-chart-placeholder {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  margin-bottom: 1.5rem;
  gap: 0.75rem;
  color: var(--ss-text-muted);
}

.cd-chart-placeholder i {
  font-size: 3rem;
  opacity: 0.2;
}

.cd-chart-placeholder p {
  font-size: 0.9375rem;
}

/* ---- Trade Flows Table ---- */
.cd-flows-section {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  overflow: hidden;
}

.cd-flows-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--ss-border-light);
}

.cd-flows-header h2 {
  font-size: 1rem;
  font-weight: 700;
  margin: 0;
}

.cd-flows-count {
  font-size: 0.75rem;
  color: var(--ss-text-muted);
  font-weight: 500;
}

.cd-flows-table-wrap {
  overflow-x: auto;
}

.cd-flows-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.cd-flows-table thead {
  background: var(--ss-bg-base);
}

.cd-flows-table th {
  text-align: left;
  padding: 0.625rem 1rem;
  color: var(--ss-text-muted);
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
  user-select: none;
}

.cd-flows-th--sortable {
  cursor: pointer;
  transition: color var(--ss-transition-fast);
}

.cd-flows-th--sortable:hover {
  color: var(--ss-text-primary);
}

.cd-flows-th--sortable i {
  font-size: 0.625rem;
  margin-left: 0.25rem;
  opacity: 0.5;
}

.cd-flows-th--right,
.cd-flows-td--right {
  text-align: right;
}

.cd-flows-table td {
  padding: 0.625rem 1rem;
  border-top: 1px solid var(--ss-border);
  color: var(--ss-text-secondary);
  font-variant-numeric: tabular-nums;
}

.cd-flows-table tbody tr {
  transition: background var(--ss-transition-fast);
}

.cd-flows-table tbody tr:hover td {
  background: var(--ss-bg-elevated);
}

.cd-flow-route {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}

.cd-flow-origin {
  color: var(--ss-text-primary);
  font-weight: 500;
}

.cd-flow-arrow {
  font-size: 0.5rem;
  color: var(--ss-text-muted);
}

.cd-flow-dest {
  color: var(--ss-text-primary);
  font-weight: 500;
}

.cd-flow-commodity {
  white-space: nowrap;
}

.cd-flows-td--muted {
  color: var(--ss-text-muted);
}

.cd-flows-empty {
  text-align: center;
  color: var(--ss-text-muted);
  padding: 2rem 1rem !important;
}

/* ---- Utilities ---- */
.mb-1 { margin-bottom: 0.25rem; }
.mb-2 { margin-bottom: 0.5rem; }
</style>
