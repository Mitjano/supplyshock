<template>
  <div class="forward-curve-chart">
    <div class="chart-controls">
      <select v-model="commodity" class="ss-select" @change="fetchData">
        <option value="crude_oil">Crude Oil (WTI)</option>
        <option value="brent">Brent</option>
        <option value="natural_gas">Natural Gas</option>
        <option value="gold">Gold</option>
      </select>
      <div class="toggle-group">
        <label v-for="p in periods" :key="p.key" class="ss-checkbox">
          <input type="checkbox" v-model="p.visible" @change="renderChart()" />
          {{ p.label }}
        </label>
      </div>
    </div>
    <div v-if="structureLabel" class="structure-badge" :class="structureClass">
      {{ structureLabel }}
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
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
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
const commodity = ref('crude_oil')
let chart: echarts.ECharts | null = null

const periods = reactive([
  { key: 'today', label: t('analytics.forwardCurve.today'), visible: true },
  { key: '1w_ago', label: t('analytics.forwardCurve.oneWeekAgo'), visible: true },
  { key: '1m_ago', label: t('analytics.forwardCurve.oneMonthAgo'), visible: false }
])

const COLORS: Record<string, string> = { today: '#3b82f6', '1w_ago': '#f59e0b', '1m_ago': '#a78bfa' }

interface CurveData {
  expiry_months: string[]
  curves: Record<string, number[]>
  structure: 'contango' | 'backwardation' | 'flat'
}
const curveData = ref<CurveData | null>(null)

const structureLabel = computed(() => {
  if (!curveData.value) return ''
  const s = curveData.value.structure
  return s === 'contango' ? t('analytics.forwardCurve.contango')
    : s === 'backwardation' ? t('analytics.forwardCurve.backwardation')
    : t('analytics.forwardCurve.flat')
})
const structureClass = computed(() => curveData.value?.structure || '')

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/forward-curve?commodity=${commodity.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    curveData.value = json.data || null
    await nextTick()
    renderChart()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !curveData.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)
  const d = curveData.value

  const series: any[] = []
  for (const p of periods) {
    if (!p.visible || !d.curves[p.key]) continue
    series.push({
      name: p.label, type: 'line', data: d.curves[p.key],
      smooth: true, symbol: 'circle', symbolSize: 4,
      lineStyle: { color: COLORS[p.key], width: p.key === 'today' ? 2.5 : 1.5 }
    })
  }

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name), textStyle: { color: '#94a3b8' } },
    grid: { left: 60, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: d.expiry_months, name: t('analytics.forwardCurve.expiry'), nameTextStyle: { color: '#64748b' }, axisLabel: { color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: { type: 'value', scale: true, name: '$/bbl', nameTextStyle: { color: '#64748b' }, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.forward-curve-chart { width: 100%; }
.chart-controls { margin-bottom: 0.75rem; display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.toggle-group { display: flex; gap: 1rem; }
.ss-checkbox { display: flex; align-items: center; gap: 0.4rem; color: var(--ss-text-secondary); font-size: 0.85rem; cursor: pointer; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.structure-badge { display: inline-block; padding: 0.2rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.75rem; }
.structure-badge.contango { background: rgba(239,68,68,0.15); color: #f87171; }
.structure-badge.backwardation { background: rgba(34,197,94,0.15); color: #4ade80; }
.structure-badge.flat { background: rgba(148,163,184,0.15); color: #94a3b8; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
