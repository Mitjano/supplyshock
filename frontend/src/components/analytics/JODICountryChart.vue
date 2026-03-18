<template>
  <div class="jodi-chart">
    <div class="chart-controls">
      <select v-model="country" class="ss-select" @change="fetchData">
        <option value="US">United States</option>
        <option value="CN">China</option>
        <option value="SA">Saudi Arabia</option>
        <option value="RU">Russia</option>
        <option value="JP">Japan</option>
        <option value="DE">Germany</option>
      </select>
      <select v-model="product" class="ss-select" @change="fetchData">
        <option value="crude_oil">Crude Oil</option>
        <option value="natural_gas">Natural Gas</option>
        <option value="gasoline">Gasoline</option>
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
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const country = ref('US')
const product = ref('crude_oil')
let chart: echarts.ECharts | null = null

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${API_BASE}/api/v1/analytics/jodi?country=${country.value}&product=${product.value}`, { headers })
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

function renderChart(data: { date: string; production: number; demand: number; stocks: number }[]) {
  if (!chartRef.value) return
  chart?.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('analytics.balance.production'), t('analytics.balance.consumption'), t('analytics.balance.endingStocks')], textStyle: { color: '#94a3b8' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: data.map(d => d.date), axisLabel: { color: '#94a3b8' } },
    yAxis: [
      { type: 'value', name: 'kb/d', axisLabel: { color: '#94a3b8' } },
      { type: 'value', name: 'mb', axisLabel: { color: '#94a3b8' } },
    ],
    series: [
      { name: t('analytics.balance.production'), type: 'bar', data: data.map(d => d.production), itemStyle: { color: '#22c55e' } },
      { name: t('analytics.balance.consumption'), type: 'bar', data: data.map(d => d.demand), itemStyle: { color: '#ef4444' } },
      { name: t('analytics.balance.endingStocks'), type: 'line', yAxisIndex: 1, data: data.map(d => d.stocks), lineStyle: { color: '#3b82f6' }, itemStyle: { color: '#3b82f6' } },
    ],
  })
}

onMounted(() => { fetchData(); window.addEventListener('resize', () => chart?.resize()) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', () => chart?.resize()) })
</script>

<style scoped>
.jodi-chart { width: 100%; }
.chart-controls { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.chart-container { width: 100%; height: 350px; }
.chart-placeholder { border-radius: var(--ss-radius); }
.error-state { display: flex; flex-direction: column; align-items: center; padding: 2rem; gap: 0.5rem; color: var(--ss-text-muted); }
.skeleton-bar { background: linear-gradient(90deg, var(--ss-bg-elevated) 25%, var(--ss-border-light) 50%, var(--ss-bg-elevated) 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; }
@keyframes skeleton-shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
</style>
