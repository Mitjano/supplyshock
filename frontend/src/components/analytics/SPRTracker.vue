<template>
  <div class="spr-tracker">
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 400px" />
    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchData">{{ t('common.retry') }}</button>
    </div>
    <template v-else>
      <!-- KPI cards -->
      <div class="spr-kpis">
        <div class="kpi-card">
          <span class="kpi-label">{{ t('analytics.spr.currentLevel') }}</span>
          <span class="kpi-value">{{ currentLevel.toFixed(1) }} <small>mb</small></span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">{{ t('analytics.spr.withdrawalRate') }}</span>
          <span class="kpi-value" :class="withdrawalRate < 0 ? 'text-danger' : 'text-success'">
            {{ withdrawalRate > 0 ? '+' : '' }}{{ withdrawalRate.toFixed(2) }} <small>mb/wk</small>
          </span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">{{ t('analytics.spr.daysOfCover') }}</span>
          <span class="kpi-value">{{ daysOfCover }}</span>
        </div>
      </div>
      <!-- Gauge + historical line -->
      <div class="spr-charts">
        <div ref="gaugeRef" class="gauge-container" />
        <div ref="lineRef" class="line-container" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@clerk/vue'
import * as echarts from 'echarts/core'
import { LineChart, GaugeChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GaugeChart, GridComponent, TooltipComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const gaugeRef = ref<HTMLElement | null>(null)
const lineRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref(false)
const currentLevel = ref(0)
const withdrawalRate = ref(0)
const daysOfCover = ref(0)
let gaugeChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null

interface SPRData {
  date: string
  level_mb: number
  capacity_mb: number
  withdrawal_rate: number
  days_of_cover: number
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/spr`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: SPRData[] = json.data || []
    if (rows.length === 0) return
    const latest = rows[rows.length - 1]
    currentLevel.value = latest.level_mb
    withdrawalRate.value = latest.withdrawal_rate
    daysOfCover.value = latest.days_of_cover
    await nextTick()
    renderGauge(latest)
    renderLine(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderGauge(latest: SPRData) {
  if (!gaugeRef.value) return
  if (gaugeChart) gaugeChart.dispose()
  gaugeChart = echarts.init(gaugeRef.value)

  const pct = (latest.level_mb / latest.capacity_mb) * 100

  gaugeChart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      progress: { show: true, width: 18, itemStyle: { color: pct < 40 ? '#ef4444' : pct < 60 ? '#f59e0b' : '#22c55e' } },
      axisLine: { lineStyle: { width: 18, color: [[1, '#1e293b']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      title: { show: true, offsetCenter: [0, '70%'], fontSize: 12, color: '#94a3b8' },
      detail: { valueAnimation: true, fontSize: 24, color: '#e2e8f0', offsetCenter: [0, '30%'], formatter: '{value}%' },
      data: [{ value: Math.round(pct), name: t('analytics.spr.fillLevel') }]
    }]
  })
}

function renderLine(rows: SPRData[]) {
  if (!lineRef.value) return
  if (lineChart) lineChart.dispose()
  lineChart = echarts.init(lineRef.value)

  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 10, top: 10, bottom: 30 },
    xAxis: {
      type: 'category',
      data: rows.map(r => r.date),
      axisLabel: { color: '#64748b', rotate: 30 },
      axisLine: { lineStyle: { color: '#334155' } }
    },
    yAxis: {
      type: 'value',
      name: 'mb',
      nameTextStyle: { color: '#64748b' },
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: '#1e293b' } }
    },
    series: [{
      type: 'line',
      data: rows.map(r => r.level_mb),
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(59,130,246,0.25)' },
        { offset: 1, color: 'rgba(59,130,246,0.02)' }
      ]) }
    }]
  })
}

onMounted(() => fetchData())
onUnmounted(() => {
  if (gaugeChart) gaugeChart.dispose()
  if (lineChart) lineChart.dispose()
})
</script>

<style scoped>
.spr-tracker { width: 100%; }
.spr-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
.kpi-card { background: var(--ss-bg-base, #0f172a); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 1rem; text-align: center; }
.kpi-label { display: block; font-size: 0.75rem; color: var(--ss-text-muted); margin-bottom: 0.25rem; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi-value { font-size: 1.5rem; font-weight: 700; color: var(--ss-text-primary); }
.kpi-value small { font-size: 0.75rem; font-weight: 400; color: var(--ss-text-muted); }
.text-danger { color: #ef4444; }
.text-success { color: #22c55e; }
.spr-charts { display: grid; grid-template-columns: 200px 1fr; gap: 1rem; }
.gauge-container { height: 200px; }
.line-container { height: 200px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
