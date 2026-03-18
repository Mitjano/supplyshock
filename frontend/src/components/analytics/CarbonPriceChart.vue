<template>
  <div class="carbon-price-chart">
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

interface CarbonRow {
  date: string
  eu_ets: number
  uk_ets: number
  us_rggi: number
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/carbon`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: CarbonRow[] = json.data || []
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: CarbonRow[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['EU ETS', 'UK ETS', 'US RGGI'],
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: {
      type: 'category',
      data: rows.map(r => r.date),
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#334155' } }
    },
    yAxis: {
      type: 'value',
      name: t('analytics.carbon.priceUnit'),
      nameTextStyle: { color: '#64748b' },
      scale: true,
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [
      {
        name: 'EU ETS',
        type: 'line',
        data: rows.map(r => r.eu_ets),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 2 }
      },
      {
        name: 'UK ETS',
        type: 'line',
        data: rows.map(r => r.uk_ets),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#8b5cf6', width: 2 }
      },
      {
        name: 'US RGGI',
        type: 'line',
        data: rows.map(r => r.us_rggi),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#22c55e', width: 2 }
      }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.carbon-price-chart { width: 100%; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
