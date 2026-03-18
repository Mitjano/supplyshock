<template>
  <div class="rig-count-chart">
    <div class="chart-controls">
      <select v-model="region" class="ss-select" @change="fetchData">
        <option value="us">US</option>
        <option value="canada">Canada</option>
        <option value="international">International</option>
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
const region = ref('us')
let chart: echarts.ECharts | null = null

interface RigData {
  date: string
  rig_count: number
  wti_price: number
  wti_price_shifted: number // WTI shifted 6 months forward
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/rigs?region=${region.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: RigData[] = json.data || []
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: RigData[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const dates = rows.map(r => r.date)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: [t('analytics.rigCount.rigs'), t('analytics.rigCount.wtiShifted')],
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 60, right: 60, top: 50, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#334155' } }
    },
    yAxis: [
      {
        type: 'value',
        name: t('analytics.rigCount.rigs'),
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#64748b' },
        splitLine: { lineStyle: { color: '#1e293b' } }
      },
      {
        type: 'value',
        name: 'WTI ($/bbl)',
        nameTextStyle: { color: '#64748b' },
        axisLabel: { color: '#64748b' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: t('analytics.rigCount.rigs'),
        type: 'bar',
        data: rows.map(r => r.rig_count),
        itemStyle: { color: 'rgba(59,130,246,0.6)' },
        barMaxWidth: 8
      },
      {
        name: t('analytics.rigCount.wtiShifted'),
        type: 'line',
        yAxisIndex: 1,
        data: rows.map(r => r.wti_price_shifted),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 2 },
        z: 10
      }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.rig-count-chart { width: 100%; }
.chart-controls { margin-bottom: 1rem; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
