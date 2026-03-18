<template>
  <div class="inventory-chart">
    <div class="chart-controls">
      <select v-model="commodity" class="ss-select" @change="fetchData">
        <option value="crude_oil">Crude Oil</option>
        <option value="natural_gas">Natural Gas</option>
        <option value="heating_oil">Heating Oil</option>
        <option value="gasoline">Gasoline</option>
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
let chart: echarts.ECharts | null = null

interface InventoryData {
  week: number // week-of-year 1..52
  five_year_min: number
  five_year_max: number
  five_year_avg: number
  previous_year: number
  current_year: number
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/inventories?commodity=${commodity.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: InventoryData[] = json.data || []
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: InventoryData[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const weeks = rows.map(r => `W${r.week}`)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [t('analytics.inventory.fiveYearRange'), t('analytics.inventory.fiveYearAvg'), t('analytics.inventory.previousYear'), t('analytics.inventory.currentYear')],
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: weeks, axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [
      // 5-year range band: lower bound (invisible)
      { name: '_min', type: 'line', data: rows.map(r => r.five_year_min), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, stack: 'range', stackStrategy: 'all', silent: true },
      // 5-year range band: upper - lower (shaded)
      { name: t('analytics.inventory.fiveYearRange'), type: 'line', data: rows.map(r => r.five_year_max - r.five_year_min), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(148,163,184,0.15)' }, stack: 'range', stackStrategy: 'all', silent: true },
      // 5-year avg
      { name: t('analytics.inventory.fiveYearAvg'), type: 'line', data: rows.map(r => r.five_year_avg), smooth: true, symbol: 'none', lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' } },
      // Previous year
      { name: t('analytics.inventory.previousYear'), type: 'line', data: rows.map(r => r.previous_year), smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1.5 } },
      // Current year (bold)
      { name: t('analytics.inventory.currentYear'), type: 'line', data: rows.map(r => r.current_year), smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 3 }, z: 10 }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.inventory-chart { width: 100%; }
.chart-controls { margin-bottom: 1rem; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
