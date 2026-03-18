<template>
  <div class="crack-spread-chart">
    <div class="chart-controls">
      <label class="ss-checkbox">
        <input type="checkbox" v-model="showSeasonal" @change="renderChart(data)" />
        {{ t('analytics.cracks.seasonalOverlay') }}
      </label>
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
const showSeasonal = ref(false)
let chart: echarts.ECharts | null = null

interface CrackRow {
  date: string
  crack_321: number
  crack_211: number
  brent_crack: number
  seasonal_321?: number
}
const data = ref<CrackRow[]>([])

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(`${API_BASE}/api/v1/analytics/crack-spreads`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    data.value = json.data || []
    await nextTick()
    renderChart(data.value)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: CrackRow[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const dates = rows.map(r => r.date)
  const series: any[] = [
    { name: '3-2-1 Crack', type: 'line', data: rows.map(r => r.crack_321), smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 2 } },
    { name: '2-1-1 Crack', type: 'line', data: rows.map(r => r.crack_211), smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 2 } },
    { name: 'Brent Crack', type: 'line', data: rows.map(r => r.brent_crack), smooth: true, symbol: 'none', lineStyle: { color: '#10b981', width: 2 } }
  ]

  if (showSeasonal.value) {
    series.push({
      name: t('analytics.cracks.seasonal321'),
      type: 'line', data: rows.map(r => r.seasonal_321 ?? null),
      smooth: true, symbol: 'none',
      lineStyle: { color: '#94a3b8', width: 1.5, type: 'dashed' }
    })
  }

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name), textStyle: { color: '#94a3b8' } },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { formatter: (v: string) => v.slice(5, 10), color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'value', scale: true, name: '$/bbl', nameTextStyle: { color: '#64748b' }, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.crack-spread-chart { width: 100%; }
.chart-controls { margin-bottom: 1rem; display: flex; gap: 1rem; align-items: center; }
.ss-checkbox { display: flex; align-items: center; gap: 0.5rem; color: var(--ss-text-secondary); font-size: 0.85rem; cursor: pointer; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
