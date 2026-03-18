<template>
  <div class="fx-panel">
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 400px" />
    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchData">{{ t('common.retry') }}</button>
    </div>
    <template v-else>
      <!-- Currency pair grid with sparklines -->
      <div class="fx-grid">
        <div v-for="pair in pairs" :key="pair.symbol" class="fx-card" :class="{ active: selectedPair === pair.symbol }" @click="selectedPair = pair.symbol">
          <div class="fx-header">
            <span class="fx-symbol">{{ pair.symbol }}</span>
            <span class="fx-rate">{{ pair.rate.toFixed(4) }}</span>
          </div>
          <div :ref="(el) => setSparkRef(pair.symbol, el as HTMLElement)" class="fx-spark" />
          <span class="fx-change" :class="pair.change >= 0 ? 'text-success' : 'text-danger'">
            {{ pair.change >= 0 ? '+' : '' }}{{ pair.change.toFixed(2) }}%
          </span>
        </div>
      </div>

      <!-- DXY overlay chart -->
      <div class="dxy-section">
        <h3 class="section-title">{{ t('analytics.fx.dxyOverlay') }}</h3>
        <div ref="dxyChartRef" class="chart-container" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@clerk/vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const loading = ref(false)
const error = ref(false)
const selectedPair = ref('EUR/USD')
const dxyChartRef = ref<HTMLElement | null>(null)
const sparkRefs: Record<string, HTMLElement> = {}
const sparkCharts: echarts.ECharts[] = []
let dxyChart: echarts.ECharts | null = null

interface FXPair {
  symbol: string
  rate: number
  change: number
  series: number[]
}

interface DXYData {
  dates: string[]
  dxy: number[]
  commodity_price: number[]
  commodity_label: string
}

const pairs = ref<FXPair[]>([])
let dxyData: DXYData | null = null

function setSparkRef(symbol: string, el: HTMLElement) {
  if (el) sparkRefs[symbol] = el
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const [pairsResp, dxyResp] = await Promise.all([
      fetch(`${API_BASE}/api/v1/fx/pairs`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API_BASE}/api/v1/fx/dxy-overlay`, { headers: { Authorization: `Bearer ${token}` } })
    ])
    if (!pairsResp.ok || !dxyResp.ok) throw new Error('fetch failed')
    const pairsJson = await pairsResp.json()
    const dxyJson = await dxyResp.json()
    pairs.value = pairsJson.data || []
    dxyData = dxyJson.data || null
    await nextTick()
    renderSparks()
    renderDxy()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderSparks() {
  sparkCharts.forEach(c => c.dispose())
  sparkCharts.length = 0

  for (const pair of pairs.value) {
    const el = sparkRefs[pair.symbol]
    if (!el) continue
    const c = echarts.init(el)
    sparkCharts.push(c)
    const isUp = pair.change >= 0
    c.setOption({
      grid: { left: 0, right: 0, top: 2, bottom: 2 },
      xAxis: { type: 'category', show: false, data: pair.series.map((_, i) => i) },
      yAxis: { type: 'value', show: false, scale: true },
      series: [{
        type: 'line', data: pair.series, smooth: true, symbol: 'none',
        lineStyle: { color: isUp ? '#22c55e' : '#ef4444', width: 1.5 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: isUp ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)' },
          { offset: 1, color: 'transparent' }
        ]) }
      }]
    })
  }
}

function renderDxy() {
  if (!dxyChartRef.value || !dxyData) return
  if (dxyChart) dxyChart.dispose()
  dxyChart = echarts.init(dxyChartRef.value)

  dxyChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['DXY', dxyData.commodity_label], textStyle: { color: '#94a3b8' } },
    grid: { left: 60, right: 60, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: dxyData.dates, axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: [
      { type: 'value', name: 'DXY', nameTextStyle: { color: '#64748b' }, scale: true, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
      { type: 'value', name: dxyData.commodity_label, nameTextStyle: { color: '#64748b' }, scale: true, axisLabel: { color: '#64748b' }, splitLine: { show: false } }
    ],
    series: [
      { name: 'DXY', type: 'line', data: dxyData.dxy, smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 2 } },
      { name: dxyData.commodity_label, type: 'line', yAxisIndex: 1, data: dxyData.commodity_price, smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 2 } }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => {
  sparkCharts.forEach(c => c.dispose())
  if (dxyChart) dxyChart.dispose()
})
</script>

<style scoped>
.fx-panel { width: 100%; }
.fx-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem; }
.fx-card { background: var(--ss-bg-base, #0f172a); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.75rem; cursor: pointer; transition: border-color 0.2s; }
.fx-card:hover, .fx-card.active { border-color: var(--ss-accent); }
.fx-header { display: flex; justify-content: space-between; align-items: baseline; }
.fx-symbol { font-size: 0.8rem; font-weight: 600; color: var(--ss-text-primary); }
.fx-rate { font-size: 0.9rem; font-weight: 700; color: var(--ss-text-primary); }
.fx-spark { height: 30px; }
.fx-change { font-size: 0.7rem; font-weight: 600; }
.text-success { color: #22c55e; }
.text-danger { color: #ef4444; }
.section-title { font-size: 0.9rem; font-weight: 600; color: var(--ss-text-primary); margin-bottom: 0.75rem; }
.dxy-section { margin-top: 1rem; }
.chart-container { height: 300px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
