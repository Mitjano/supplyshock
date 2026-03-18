<template>
  <div class="port-analytics">
    <!-- Port metric cards with sparklines -->
    <div v-if="loading" class="port-cards">
      <div v-for="i in 6" :key="i" class="ss-card port-card skeleton-card">
        <div class="skeleton-line skeleton-title" />
        <div class="skeleton-line skeleton-value" />
        <div class="skeleton-line skeleton-bar" />
      </div>
    </div>

    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchData">{{ t('common.retry') }}</button>
    </div>

    <template v-else>
      <div class="port-cards">
        <div v-for="port in topPorts" :key="port.port_id" class="ss-card port-card">
          <div class="port-card-header">
            <span class="port-name">{{ port.name }}</span>
            <span class="port-country text-muted">{{ port.country }}</span>
          </div>
          <div class="port-metrics">
            <div class="metric">
              <span class="metric-label text-muted">{{ t('analytics.port.vessels') }}</span>
              <span class="metric-value">{{ port.vessel_count }}</span>
            </div>
            <div class="metric">
              <span class="metric-label text-muted">{{ t('analytics.port.waitDays') }}</span>
              <span class="metric-value">{{ port.avg_wait_days.toFixed(1) }}</span>
            </div>
            <div class="metric">
              <span class="metric-label text-muted">{{ t('analytics.port.throughput') }}</span>
              <span class="metric-value">{{ (port.throughput_mt / 1e6).toFixed(1) }}M</span>
            </div>
          </div>
          <div class="sparkline" :ref="(el) => registerSparkline(el as HTMLElement, port.port_id, port.history)" />
        </div>
      </div>

      <!-- Rankings table -->
      <div class="ss-card rankings-card">
        <h3>{{ t('analytics.port.rankings') }}</h3>
        <table class="ss-table">
          <thead>
            <tr>
              <th>#</th>
              <th>{{ t('analytics.port.portName') }}</th>
              <th>{{ t('analytics.port.vessels') }}</th>
              <th>{{ t('analytics.port.waitDays') }}</th>
              <th>{{ t('analytics.port.throughput') }}</th>
              <th>{{ t('analytics.port.congestionIdx') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(port, idx) in allPorts" :key="port.port_id">
              <td>{{ idx + 1 }}</td>
              <td><strong>{{ port.name }}</strong> <span class="text-muted">{{ port.country }}</span></td>
              <td>{{ port.vessel_count }}</td>
              <td>{{ port.avg_wait_days.toFixed(1) }}</td>
              <td>{{ (port.throughput_mt / 1e6).toFixed(1) }}M MT</td>
              <td>
                <span class="congestion-badge" :class="congestionClass(port.congestion_index)">
                  {{ port.congestion_index.toFixed(2) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
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
const sparklineInstances = new Map<string, echarts.ECharts>()

interface PortData {
  port_id: string
  name: string
  country: string
  vessel_count: number
  avg_wait_days: number
  throughput_mt: number
  congestion_index: number
  history: number[]
}
const allPorts = ref<PortData[]>([])
const topPorts = ref<PortData[]>([])

async function fetchData() {
  loading.value = true
  error.value = false
  try {
    const token = await getToken.value()
    const resp = await fetch(`${API_BASE}/api/v1/analytics/ports`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    allPorts.value = (json.data || []).sort((a: PortData, b: PortData) => b.congestion_index - a.congestion_index)
    topPorts.value = allPorts.value.slice(0, 6)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function registerSparkline(el: HTMLElement | null, id: string, history: number[]) {
  if (!el || sparklineInstances.has(id) || !history?.length) return
  const c = echarts.init(el)
  c.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { show: false, type: 'category' },
    yAxis: { show: false, type: 'value', scale: true },
    series: [{ type: 'line', data: history, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#3b82f6' }, areaStyle: { color: 'rgba(59,130,246,0.1)' } }]
  })
  sparklineInstances.set(id, c)
}

function congestionClass(idx: number): string {
  if (idx >= 0.8) return 'critical'
  if (idx >= 0.6) return 'high'
  if (idx >= 0.4) return 'elevated'
  return 'normal'
}

onMounted(() => fetchData())
onUnmounted(() => { sparklineInstances.forEach(c => c.dispose()); sparklineInstances.clear() })
</script>

<style scoped>
.port-analytics { width: 100%; }
.port-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.port-card { padding: 1rem; }
.port-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.port-name { font-weight: 600; font-size: 0.95rem; }
.port-country { font-size: 0.75rem; }
.port-metrics { display: flex; gap: 1rem; margin-bottom: 0.5rem; }
.metric { display: flex; flex-direction: column; }
.metric-label { font-size: 0.7rem; }
.metric-value { font-size: 1rem; font-weight: 700; }
.sparkline { height: 40px; }
.rankings-card { padding: 1.5rem; }
.rankings-card h3 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
.congestion-badge { padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.congestion-badge.critical { background: rgba(239,68,68,0.15); color: #f87171; }
.congestion-badge.high { background: rgba(251,146,60,0.15); color: #fb923c; }
.congestion-badge.elevated { background: rgba(251,191,36,0.15); color: #fbbf24; }
.congestion-badge.normal { background: rgba(34,197,94,0.15); color: #4ade80; }
.skeleton-card { animation: pulse 1.5s ease-in-out infinite; }
.skeleton-title { height: 1rem; width: 60%; background: var(--bg-hover, #2a2a3e); border-radius: 4px; margin-bottom: 0.5rem; }
.skeleton-value { height: 1.5rem; width: 40%; background: var(--bg-hover, #2a2a3e); border-radius: 4px; margin-bottom: 0.5rem; }
.skeleton-bar { height: 40px; background: var(--bg-hover, #2a2a3e); border-radius: 4px; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
