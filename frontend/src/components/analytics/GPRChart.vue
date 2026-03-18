<template>
  <div class="gpr-chart">
    <div class="chart-controls">
      <select v-model="range" class="ss-select" @change="fetchData">
        <option value="1Y">1Y</option>
        <option value="5Y">5Y</option>
        <option value="10Y">10Y</option>
      </select>
    </div>
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 350px" />
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
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const range = ref('5Y')
let chart: echarts.ECharts | null = null

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${API_BASE}/api/v1/macro/gpr?range=${range.value}`, { headers })
    if (!res.ok) throw new Error()
    const body = await res.json()
    await nextTick()
    renderChart(body.data)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(data: { date: string; gpr: number; gpr_threats: number }[]) {
  if (!chartRef.value) return
  chart?.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('macro.uncertainty.gpr'), 'GPR Threats'], textStyle: { color: '#94a3b8' } },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: data.map(d => d.date), axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      { name: t('macro.uncertainty.gpr'), type: 'line', data: data.map(d => d.gpr), smooth: true, lineStyle: { color: '#ef4444' }, itemStyle: { color: '#ef4444' } },
      { name: 'GPR Threats', type: 'line', data: data.map(d => d.gpr_threats), smooth: true, lineStyle: { color: '#f59e0b' }, itemStyle: { color: '#f59e0b' } },
    ],
  })
}

onMounted(() => { fetchData(); window.addEventListener('resize', () => chart?.resize()) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', () => chart?.resize()) })
</script>

<style scoped>
.gpr-chart { width: 100%; }
.chart-controls { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.chart-container { width: 100%; height: 350px; }
.chart-placeholder { border-radius: var(--ss-radius); }
.error-state { display: flex; flex-direction: column; align-items: center; padding: 2rem; gap: 0.5rem; color: var(--ss-text-muted); }
.skeleton-bar { background: linear-gradient(90deg, var(--ss-bg-elevated) 25%, var(--ss-border-light) 50%, var(--ss-bg-elevated) 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; }
@keyframes skeleton-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
</style>
