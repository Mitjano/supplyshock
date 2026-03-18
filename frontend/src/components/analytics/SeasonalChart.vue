<template>
  <div class="seasonal-chart">
    <div class="chart-controls">
      <select v-model="commodity" class="ss-select" @change="fetchData">
        <option value="crude_oil">Crude Oil</option>
        <option value="natural_gas">Natural Gas</option>
        <option value="gold">Gold</option>
        <option value="wheat">Wheat</option>
      </select>
      <select v-model="selectedYear" class="ss-select" @change="fetchData">
        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
      </select>
    </div>
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 400px" />
    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchData">{{ t('common.retry') }}</button>
    </div>
    <div v-else ref="chartRef" class="chart-container" />
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

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const commodity = ref('crude_oil')
const currentYear = new Date().getFullYear()
const selectedYear = ref(currentYear)
const years = Array.from({ length: 5 }, (_, i) => currentYear - i)
let chart: echarts.ECharts | null = null

interface SeasonalRow {
  day_of_year: number
  p10: number
  p25: number
  p50: number
  p75: number
  p90: number
  current: number
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/seasonal?commodity=${commodity.value}&year=${selectedYear.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: SeasonalRow[] = json.data || []
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: SeasonalRow[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const days = rows.map(r => r.day_of_year)
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['P10-P90', 'P25-P75', t('analytics.seasonal.median'), `${selectedYear.value}`],
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: {
      type: 'category', data: days,
      axisLabel: { formatter: (v: string) => { const d = parseInt(v); return months[Math.floor((d - 1) / 30.4)] || '' }, color: '#64748b', interval: 29 },
      axisLine: { lineStyle: { color: '#334155' } }
    },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [
      // p10 base (invisible)
      { name: '_p10', type: 'line', data: rows.map(r => r.p10), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, stack: 'outer', stackStrategy: 'all', silent: true },
      // p10-p90 band
      { name: 'P10-P90', type: 'line', data: rows.map(r => r.p90 - r.p10), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(59,130,246,0.08)' }, stack: 'outer', stackStrategy: 'all', silent: true },
      // p25 base (invisible)
      { name: '_p25', type: 'line', data: rows.map(r => r.p25), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, stack: 'inner', stackStrategy: 'all', silent: true },
      // p25-p75 band
      { name: 'P25-P75', type: 'line', data: rows.map(r => r.p75 - r.p25), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(59,130,246,0.15)' }, stack: 'inner', stackStrategy: 'all', silent: true },
      // Median
      { name: t('analytics.seasonal.median'), type: 'line', data: rows.map(r => r.p50), smooth: true, symbol: 'none', lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' } },
      // Current year (bold)
      { name: `${selectedYear.value}`, type: 'line', data: rows.map(r => r.current), smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 3 }, z: 10 }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.seasonal-chart { width: 100%; }
.chart-controls { margin-bottom: 1rem; display: flex; gap: 0.75rem; flex-wrap: wrap; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
