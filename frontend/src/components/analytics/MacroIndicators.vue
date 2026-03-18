<template>
  <div class="macro-indicators">
    <div v-if="loading" class="chart-placeholder skeleton-bar" style="height: 300px" />
    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchData">{{ t('common.retry') }}</button>
    </div>
    <div v-else class="indicators-grid">
      <div v-for="ind in indicators" :key="ind.key" class="indicator-card">
        <div class="ind-header">
          <span class="ind-label">{{ ind.label }}</span>
          <span class="ind-value" :class="ind.changeClass">{{ ind.display }}</span>
        </div>
        <div :ref="(el) => setSparkRef(ind.key, el as HTMLElement)" class="spark-container" />
        <span class="ind-change" :class="ind.changeClass">{{ ind.changeText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@clerk/vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, CanvasRenderer])

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const loading = ref(false)
const error = ref(false)
const sparkRefs: Record<string, HTMLElement> = {}
const sparkCharts: echarts.ECharts[] = []

interface IndicatorRow {
  key: string
  label: string
  current: number
  change_pct: number
  series: number[]
}

interface DisplayIndicator {
  key: string
  label: string
  display: string
  changeText: string
  changeClass: string
  series: number[]
}

const indicators = ref<DisplayIndicator[]>([])

function setSparkRef(key: string, el: HTMLElement) {
  if (el) sparkRefs[key] = el
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/macro/indicators`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: IndicatorRow[] = json.data || []

    indicators.value = rows.map(r => ({
      key: r.key,
      label: r.label,
      display: r.current.toFixed(2),
      changeText: `${r.change_pct >= 0 ? '+' : ''}${r.change_pct.toFixed(2)}%`,
      changeClass: r.change_pct >= 0 ? 'text-success' : 'text-danger',
      series: r.series
    }))

    await nextTick()
    renderSparks()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderSparks() {
  sparkCharts.forEach(c => c.dispose())
  sparkCharts.length = 0

  for (const ind of indicators.value) {
    const el = sparkRefs[ind.key]
    if (!el) continue
    const c = echarts.init(el)
    sparkCharts.push(c)
    const isUp = ind.series[ind.series.length - 1] >= ind.series[0]
    c.setOption({
      grid: { left: 0, right: 0, top: 2, bottom: 2 },
      xAxis: { type: 'category', show: false, data: ind.series.map((_, i) => i) },
      yAxis: { type: 'value', show: false, scale: true },
      series: [{
        type: 'line',
        data: ind.series,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: isUp ? '#22c55e' : '#ef4444', width: 1.5 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: isUp ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)' },
            { offset: 1, color: 'transparent' }
          ])
        }
      }]
    })
  }
}

onMounted(() => fetchData())
onUnmounted(() => sparkCharts.forEach(c => c.dispose()))
</script>

<style scoped>
.macro-indicators { width: 100%; }
.indicators-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
.indicator-card { background: var(--ss-bg-base, #0f172a); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.75rem 1rem; }
.ind-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.25rem; }
.ind-label { font-size: 0.75rem; color: var(--ss-text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.ind-value { font-size: 1.1rem; font-weight: 700; color: var(--ss-text-primary); }
.spark-container { height: 40px; }
.ind-change { font-size: 0.75rem; font-weight: 600; }
.text-success { color: #22c55e; }
.text-danger { color: #ef4444; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
