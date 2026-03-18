<template>
  <div class="correlation-matrix">
    <div class="chart-controls">
      <div class="window-tabs">
        <button
          v-for="w in windows"
          :key="w.days"
          class="tab-btn tab-btn--sm"
          :class="{ active: selectedWindow === w.days }"
          @click="selectedWindow = w.days; fetchData()"
        >{{ w.label }}</button>
      </div>
    </div>
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 450px" />
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
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const selectedWindow = ref(30)
let chart: echarts.ECharts | null = null

const windows = [
  { days: 7, label: '7D' },
  { days: 30, label: '30D' },
  { days: 90, label: '90D' }
]

interface CorrData {
  commodities: string[]
  matrix: number[][] // NxN
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/correlations?window=${selectedWindow.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const corrData: CorrData = json.data || { commodities: [], matrix: [] }
    await nextTick()
    renderChart(corrData)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function formatName(c: string): string {
  return c.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function renderChart(d: CorrData) {
  if (!chartRef.value || d.commodities.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const labels = d.commodities.map(formatName)
  const heatData: [number, number, number][] = []
  for (let i = 0; i < d.matrix.length; i++) {
    for (let j = 0; j < d.matrix[i].length; j++) {
      heatData.push([j, i, parseFloat(d.matrix[i][j].toFixed(2))])
    }
  }

  chart.setOption({
    tooltip: {
      formatter: (p: any) => `${labels[p.value[1]]} / ${labels[p.value[0]]}: <strong>${p.value[2]}</strong>`
    },
    grid: { left: 100, right: 60, top: 20, bottom: 80 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, color: '#94a3b8', fontSize: 11 }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'category', data: labels, axisLabel: { color: '#94a3b8', fontSize: 11 }, axisLine: { lineStyle: { color: '#334155' } } },
    visualMap: {
      min: -1, max: 1, calculable: true, orient: 'vertical', right: 0, top: 'center',
      inRange: { color: ['#ef4444', '#fbbf24', '#f8fafc', '#38bdf8', '#3b82f6'] },
      textStyle: { color: '#94a3b8' }
    },
    series: [{
      type: 'heatmap',
      data: heatData,
      label: { show: true, formatter: (p: any) => p.value[2].toFixed(2), fontSize: 10, color: '#e2e8f0' },
      itemStyle: { borderWidth: 1, borderColor: '#0f172a' }
    }]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.correlation-matrix { width: 100%; }
.chart-controls { margin-bottom: 1rem; }
.window-tabs { display: flex; gap: 0.25rem; }
.tab-btn { padding: 0.5rem 1rem; border-radius: 8px; border: 1px solid var(--border-color, #2a2a3e); background: transparent; color: var(--text-secondary, #94a3b8); cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
.tab-btn:hover { background: var(--bg-hover, rgba(255,255,255,0.05)); }
.tab-btn.active { background: var(--accent, #3b82f6); color: white; border-color: transparent; }
.tab-btn--sm { padding: 0.3rem 0.7rem; font-size: 0.8rem; }
.chart-container { height: 450px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
