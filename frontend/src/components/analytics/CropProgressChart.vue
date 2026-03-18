<template>
  <div class="crop-progress-chart">
    <div class="chart-controls">
      <select v-model="crop" class="ss-select" @change="fetchData">
        <option value="corn">Corn</option>
        <option value="soybeans">Soybeans</option>
        <option value="wheat">Wheat</option>
        <option value="cotton">Cotton</option>
      </select>
      <select v-model="view" class="ss-select">
        <option value="condition">{{ t('analytics.crops.condition') }}</option>
        <option value="exports">{{ t('analytics.crops.exports') }}</option>
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
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
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
const crop = ref('corn')
const view = ref('condition')
let chart: echarts.ECharts | null = null

interface ConditionData {
  week: string
  excellent: number
  good: number
  fair: number
  poor: number
  very_poor: number
}

interface ExportData {
  week: string
  export_sales: number
  cumulative: number
}

let conditionRows: ConditionData[] = []
let exportRows: ExportData[] = []

watch(view, () => renderCurrent())

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/crops?crop=${crop.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    conditionRows = json.condition || []
    exportRows = json.exports || []
    await nextTick()
    renderCurrent()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderCurrent() {
  if (view.value === 'condition') renderCondition()
  else renderExports()
}

function renderCondition() {
  if (!chartRef.value || conditionRows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const weeks = conditionRows.map(r => r.week)
  const colors = { excellent: '#22c55e', good: '#86efac', fair: '#fbbf24', poor: '#f97316', very_poor: '#ef4444' }
  const labels: Record<string, string> = {
    excellent: t('analytics.crops.excellent'),
    good: t('analytics.crops.good'),
    fair: t('analytics.crops.fair'),
    poor: t('analytics.crops.poor'),
    very_poor: t('analytics.crops.veryPoor')
  }

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: Object.values(labels), textStyle: { color: '#94a3b8' } },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: weeks, axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#64748b', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: (['excellent', 'good', 'fair', 'poor', 'very_poor'] as const).map(key => ({
      name: labels[key],
      type: 'line' as const,
      stack: 'condition',
      areaStyle: { color: colors[key], opacity: 0.8 },
      lineStyle: { width: 0 },
      symbol: 'none',
      data: conditionRows.map(r => r[key]),
      emphasis: { focus: 'series' as const }
    }))
  })
}

function renderExports() {
  if (!chartRef.value || exportRows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('analytics.crops.weeklySales'), t('analytics.crops.cumulative')], textStyle: { color: '#94a3b8' } },
    grid: { left: 60, right: 60, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: exportRows.map(r => r.week), axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: [
      { type: 'value', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
      { type: 'value', axisLabel: { color: '#64748b' }, splitLine: { show: false } }
    ],
    series: [
      { name: t('analytics.crops.weeklySales'), type: 'bar', data: exportRows.map(r => r.export_sales), itemStyle: { color: 'rgba(59,130,246,0.6)' }, barMaxWidth: 12 },
      { name: t('analytics.crops.cumulative'), type: 'line', yAxisIndex: 1, data: exportRows.map(r => r.cumulative), smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 2 } }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.crop-progress-chart { width: 100%; }
.chart-controls { display: flex; gap: 0.75rem; margin-bottom: 1rem; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
