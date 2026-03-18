<template>
  <div class="natgas-storage-chart">
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
let chart: echarts.ECharts | null = null

interface StorageData {
  week: number
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
      `${API_BASE}/api/v1/analytics/inventories?commodity=natural_gas`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: StorageData[] = json.data || []
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: StorageData[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const weeks = rows.map(r => `W${r.week}`)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [
        t('analytics.natGas.fiveYearRange'),
        t('analytics.natGas.fiveYearAvg'),
        t('analytics.natGas.previousYear'),
        t('analytics.natGas.currentYear')
      ],
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: weeks, axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: {
      type: 'value',
      name: 'Bcf',
      nameTextStyle: { color: '#64748b' },
      scale: true,
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [
      { name: '_min', type: 'line', data: rows.map(r => r.five_year_min), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, stack: 'range', stackStrategy: 'all', silent: true },
      { name: t('analytics.natGas.fiveYearRange'), type: 'line', data: rows.map(r => r.five_year_max - r.five_year_min), smooth: true, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(148,163,184,0.15)' }, stack: 'range', stackStrategy: 'all', silent: true },
      { name: t('analytics.natGas.fiveYearAvg'), type: 'line', data: rows.map(r => r.five_year_avg), smooth: true, symbol: 'none', lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' } },
      { name: t('analytics.natGas.previousYear'), type: 'line', data: rows.map(r => r.previous_year), smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1.5 } },
      { name: t('analytics.natGas.currentYear'), type: 'line', data: rows.map(r => r.current_year), smooth: true, symbol: 'none', lineStyle: { color: '#22c55e', width: 3 }, z: 10 }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.natgas-storage-chart { width: 100%; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
