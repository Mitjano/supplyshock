<template>
  <div class="world-trade-chart">
    <div class="chart-controls">
      <select v-model="metric" class="ss-select" @change="fetchData">
        <option value="imports">{{ t('macro.trade.imports') }}</option>
        <option value="exports">{{ t('macro.trade.exports') }}</option>
        <option value="balance">{{ t('macro.trade.balance') }}</option>
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
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const metric = ref('imports')
let chart: echarts.ECharts | null = null

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${API_BASE}/api/v1/macro/trade?metric=${metric.value}`, { headers })
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

function renderChart(data: { country: string; value: number }[]) {
  if (!chartRef.value) return
  chart?.dispose()
  chart = echarts.init(chartRef.value)
  const sorted = [...data].sort((a, b) => b.value - a.value).slice(0, 15)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'category', data: sorted.map(d => d.country).reverse(), axisLabel: { color: '#94a3b8' } },
    series: [{ type: 'bar', data: sorted.map(d => d.value).reverse(), itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] } }],
  })
}

onMounted(() => { fetchData(); window.addEventListener('resize', () => chart?.resize()) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', () => chart?.resize()) })
</script>

<style scoped>
.world-trade-chart { width: 100%; }
.chart-controls { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.chart-container { width: 100%; height: 350px; }
.chart-placeholder { border-radius: var(--ss-radius); }
.error-state { display: flex; flex-direction: column; align-items: center; padding: 2rem; gap: 0.5rem; color: var(--ss-text-muted); }
.skeleton-bar { background: linear-gradient(90deg, var(--ss-bg-elevated) 25%, var(--ss-border-light) 50%, var(--ss-bg-elevated) 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; }
@keyframes skeleton-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
</style>
