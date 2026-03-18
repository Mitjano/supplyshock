<template>
  <div class="cot-chart">
    <div class="chart-controls">
      <select v-model="commodity" class="ss-select" @change="fetchData">
        <option value="crude_oil">Crude Oil</option>
        <option value="natural_gas">Natural Gas</option>
        <option value="gold">Gold</option>
        <option value="copper">Copper</option>
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
const commodity = ref('crude_oil')
let chart: echarts.ECharts | null = null

interface COTRow {
  date: string
  commercial_net: number
  managed_money_net: number
  price: number
}

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/analytics/cot?commodity=${commodity.value}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    const rows: COTRow[] = json.data || []
    await nextTick()
    renderChart(rows)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function renderChart(rows: COTRow[]) {
  if (!chartRef.value || rows.length === 0) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const dates = rows.map(r => r.date)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('analytics.cot.commercial'), t('analytics.cot.managedMoney'), t('analytics.cot.price')], textStyle: { color: '#94a3b8' } },
    grid: { left: 60, right: 60, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { formatter: (v: string) => v.slice(5, 10), color: '#64748b' }, axisLine: { lineStyle: { color: '#334155' } } },
    yAxis: [
      { type: 'value', name: t('analytics.cot.contracts'), nameTextStyle: { color: '#64748b' }, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
      { type: 'value', name: t('analytics.cot.price'), nameTextStyle: { color: '#64748b' }, axisLabel: { color: '#64748b' }, splitLine: { show: false } }
    ],
    series: [
      { name: t('analytics.cot.commercial'), type: 'bar', data: rows.map(r => r.commercial_net), itemStyle: { color: '#3b82f6' }, barGap: '10%' },
      { name: t('analytics.cot.managedMoney'), type: 'bar', data: rows.map(r => r.managed_money_net), itemStyle: { color: '#f59e0b' } },
      { name: t('analytics.cot.price'), type: 'line', yAxisIndex: 1, data: rows.map(r => r.price), smooth: true, symbol: 'none', lineStyle: { color: '#ef4444', width: 2 } }
    ]
  })
}

onMounted(() => fetchData())
onUnmounted(() => { if (chart) chart.dispose() })
</script>

<style scoped>
.cot-chart { width: 100%; }
.chart-controls { margin-bottom: 1rem; }
.ss-select { background: var(--ss-bg-surface); color: var(--ss-text-primary); border: 1px solid var(--ss-border-light); border-radius: var(--ss-radius); padding: 0.4rem 0.75rem; font-size: 0.85rem; }
.chart-container { height: 400px; }
.chart-placeholder { background: var(--bg-hover, #2a2a3e); border-radius: 4px; animation: pulse 1.5s ease-in-out infinite; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
