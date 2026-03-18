<template>
  <div class="bunker-price-chart">
    <div class="chart-controls">
      <select v-model="port" class="ss-select" @change="fetchData">
        <option value="singapore">Singapore</option>
        <option value="rotterdam">Rotterdam</option>
        <option value="fujairah">Fujairah</option>
        <option value="houston">Houston</option>
      </select>
      <span v-if="isProxy" class="proxy-badge">
        <i class="pi pi-info-circle" />
        {{ t('analytics.bunker.estimated') }}
      </span>
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
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const port = ref('singapore')
const isProxy = ref(false)
let chart: echarts.ECharts | null = null

interface BunkerRow {
  date: string
  vlsfo: number
  hsfo: number
  mgo: number
  is_proxy: boolean
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/bunker?port=${port.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: BunkerRow[] = json.data || []
    isProxy.value = rows.some(r => r.is_proxy)
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: BunkerRow[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['VLSFO', 'HSFO', 'MGO'],
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
      name: '$/mt',
      nameTextStyle: { color: '#64748b' },
      scale: true,
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [
      { name: 'VLSFO', type: 'line', data: rows.map(r => r.vlsfo), smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 2 } },
      { name: 'HSFO', type: 'line', data: rows.map(r => r.hsfo), smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 2 } },
      { name: 'MGO', type: 'line', data: rows.map(r => r.mgo), smooth: true, symbol: 'none', lineStyle: { color: '#8b5cf6', width: 2 } }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.bunker-price-chart { width: 100%; }
.chart-controls { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1rem; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.proxy-badge { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; color: #f59e0b; background: rgba(245,158,11,0.1); padding: 0.25rem 0.6rem; border-radius: 9999px; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
