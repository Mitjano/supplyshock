<template>
  <div class="warehouse-chart">
    <div class="chart-controls">
      <select v-model="commodity" class="ss-select" @change="fetchData">
        <option value="crude_oil">Crude Oil</option>
        <option value="copper">Copper</option>
        <option value="aluminium">Aluminium</option>
        <option value="nickel">Nickel</option>
        <option value="iron_ore">Iron Ore</option>
      </select>
      <select v-model="exchange" class="ss-select" @change="fetchData">
        <option value="all">All Exchanges</option>
        <option value="lme">LME</option>
        <option value="comex">COMEX</option>
        <option value="shfe">SHFE</option>
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
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const commodity = ref('copper')
const exchange = ref('all')
let chart: echarts.ECharts | null = null

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${API_BASE}/api/v1/analytics/warehouse-stocks?commodity=${commodity.value}&exchange=${exchange.value}`, { headers })
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

function renderChart(data: { date: string; stocks: number; change: number }[]) {
  if (!chartRef.value) return
  chart?.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Stocks', 'Daily Change'], textStyle: { color: '#94a3b8' } },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: data.map(d => d.date), axisLabel: { color: '#94a3b8' } },
    yAxis: [
      { type: 'value', name: 'Tonnes', axisLabel: { color: '#94a3b8' } },
      { type: 'value', name: 'Change', axisLabel: { color: '#94a3b8' } },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      {
        name: 'Stocks', type: 'line', data: data.map(d => d.stocks), smooth: true,
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(59,130,246,0.3)' }, { offset: 1, color: 'rgba(59,130,246,0.02)' }]) },
        lineStyle: { color: '#3b82f6' }, itemStyle: { color: '#3b82f6' },
      },
      {
        name: 'Daily Change', type: 'bar', yAxisIndex: 1, data: data.map(d => d.change),
        itemStyle: { color: (p: any) => p.value >= 0 ? '#22c55e' : '#ef4444' },
      },
    ],
  })
}

onMounted(() => { fetchData(); window.addEventListener('resize', () => chart?.resize()) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', () => chart?.resize()) })
</script>

<style scoped>
.warehouse-chart { width: 100%; }
.chart-controls { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.chart-container { width: 100%; height: 350px; }
.chart-placeholder { border-radius: var(--ss-radius); }
.error-state { display: flex; flex-direction: column; align-items: center; padding: 2rem; gap: 0.5rem; color: var(--ss-text-muted); }
.skeleton-bar { background: linear-gradient(90deg, var(--ss-bg-elevated) 25%, var(--ss-border-light) 50%, var(--ss-bg-elevated) 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; }
@keyframes skeleton-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
</style>
