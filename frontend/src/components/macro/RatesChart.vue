<template>
  <div class="rates-chart">
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 400px" />
    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchData">{{ t('common.retry') }}</button>
    </div>
    <template v-else>
      <!-- Rates time series -->
      <div ref="ratesRef" class="chart-container" />
      <!-- Yield curve snapshot -->
      <h3 class="section-title">{{ t('macro.rates.yieldCurve') }}</h3>
      <div ref="curveRef" class="chart-container-sm" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@clerk/vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const ratesRef = ref<HTMLElement | null>(null)
const curveRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
let ratesChart: echarts.ECharts | null = null
let curveChart: echarts.ECharts | null = null

interface RatesRow {
  date: string
  fed_funds: number
  us_10y: number
  us_2y: number
}

interface YieldPoint {
  tenor: string
  yield: number
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const [ratesResp, curveResp] = await Promise.all([
      fetch(`${API_BASE}/api/v1/macro/rates`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API_BASE}/api/v1/macro/yield-curve`, { headers: { Authorization: `Bearer ${token}` } })
    ])
    if (!ratesResp.ok || !curveResp.ok) throw new Error('fetch failed')
    const ratesJson = await ratesResp.json()
    const curveJson = await curveResp.json()
    await nextTick()
    renderRates(ratesJson.data || [])
    renderCurve(curveJson.data || [])
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderRates(rows: RatesRow[]) {
  if (!ratesRef.value || rows.length === 0) return
  if (ratesChart) ratesChart.dispose()
  ratesChart = echarts.init(ratesRef.value)

  ratesChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [t('macro.rates.fedFunds'), t('macro.rates.us10y'), t('macro.rates.us2y')],
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: rows.map(r => r.date), axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#64748b', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [
      { name: t('macro.rates.fedFunds'), type: 'line', data: rows.map(r => r.fed_funds), smooth: true, symbol: 'none', lineStyle: { color: '#ef4444', width: 2 } },
      { name: t('macro.rates.us10y'), type: 'line', data: rows.map(r => r.us_10y), smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 2 } },
      { name: t('macro.rates.us2y'), type: 'line', data: rows.map(r => r.us_2y), smooth: true, symbol: 'none', lineStyle: { color: '#8b5cf6', width: 2, type: 'dashed' } }
    ]
  })
}

function renderCurve(points: YieldPoint[]) {
  if (!curveRef.value || points.length === 0) return
  if (curveChart) curveChart.dispose()
  curveChart = echarts.init(curveRef.value)

  curveChart.setOption({
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: points.map(p => p.tenor), axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#64748b', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [{
      type: 'line',
      data: points.map(p => p.yield),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#3b82f6', width: 2 },
      itemStyle: { color: '#3b82f6' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59,130,246,0.2)' },
          { offset: 1, color: 'rgba(59,130,246,0.02)' }
        ])
      }
    }]
  })
}

onMounted(() => fetchData())
onUnmounted(() => {
  if (ratesChart) ratesChart.dispose()
  if (curveChart) curveChart.dispose()
})
</script>

<style scoped>
.rates-chart { width: 100%; }
.chart-container { height: 350px; }
.chart-container-sm { height: 250px; }
.section-title { font-size: 0.9rem; font-weight: 600; color: var(--ss-text-primary); margin: 1.5rem 0 0.75rem; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
