<template>
  <div class="view-container fade-in">
    <!-- Welcome header -->
    <div class="dashboard-header">
      <div>
        <h1>{{ t('dashboard.welcome', { name: userName }) }}</h1>
        <p class="text-secondary">{{ t('dashboard.title') }} &mdash; {{ formattedDate }}</p>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-grid">
      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--danger">
          <i class="pi pi-bell" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ kpis.activeAlerts }}</span>
          <span class="kpi-label">{{ t('dashboard.activeAlerts') }}</span>
        </div>
      </div>

      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--info">
          <i class="pi pi-compass" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ kpis.vesselsTracked }}</span>
          <span class="kpi-label">{{ t('dashboard.vesselTracking') }}</span>
        </div>
      </div>

      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--accent">
          <i class="pi pi-chart-line" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ kpis.commoditiesMonitored }}</span>
          <span class="kpi-label">{{ t('dashboard.commoditiesMonitored') }}</span>
        </div>
      </div>

      <div class="ss-card kpi-card">
        <div class="kpi-icon" :class="bottleneckRiskClass">
          <i class="pi pi-exclamation-triangle" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ kpis.bottleneckRisk }}</span>
          <span class="kpi-label">{{ t('dashboard.bottleneckRisk') }}</span>
        </div>
      </div>
    </div>

    <!-- Two-column content -->
    <div class="dashboard-grid">
      <!-- Recent Alerts -->
      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('dashboard.recentAlerts') }}</h3>
          <router-link :to="localePath('/alerts')" class="card-link">
            {{ t('dashboard.viewAll') }} <i class="pi pi-arrow-right" />
          </router-link>
        </div>
        <div v-if="loadingAlerts" class="card-loading">
          <i class="pi pi-spin pi-spinner" /> {{ t('common.loading') }}
        </div>
        <div v-else-if="recentAlerts.length === 0" class="card-empty">
          {{ t('alerts.noAlerts') }}
        </div>
        <ul v-else class="alert-list">
          <li
            v-for="alert in recentAlerts"
            :key="alert.id"
            class="alert-item"
          >
            <span class="alert-severity" :class="`alert-severity--${alert.severity}`">
              <i :class="severityIcon(alert.severity)" />
            </span>
            <div class="alert-content">
              <span class="alert-title">{{ alert.title }}</span>
              <span class="alert-meta text-muted">{{ alert.commodity }} &middot; {{ formatTime(alert.created_at) }}</span>
            </div>
          </li>
        </ul>
      </div>

      <!-- Commodity Top Movers -->
      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('dashboard.topMovers') }}</h3>
          <router-link :to="localePath('/commodities')" class="card-link">
            {{ t('dashboard.viewAll') }} <i class="pi pi-arrow-right" />
          </router-link>
        </div>
        <div v-if="loadingPrices" class="card-loading">
          <i class="pi pi-spin pi-spinner" /> {{ t('common.loading') }}
        </div>
        <div v-else-if="topMovers.length === 0" class="card-empty">
          {{ t('common.noData') }}
        </div>
        <ul v-else class="mover-list">
          <li
            v-for="commodity in topMovers"
            :key="commodity.symbol"
            class="mover-item"
          >
            <div class="mover-info">
              <span class="mover-name">{{ commodity.name }}</span>
              <span class="mover-price text-muted">${{ commodity.price.toFixed(2) }}</span>
            </div>
            <div class="mover-sparkline" ref="sparklineRefs">
              <div :ref="(el) => registerSparkline(el as HTMLElement, commodity.symbol)" class="sparkline-chart" />
            </div>
            <span
              class="mover-change"
              :class="commodity.change >= 0 ? 'text-success' : 'text-danger'"
            >
              <i :class="commodity.change >= 0 ? 'pi pi-arrow-up' : 'pi pi-arrow-down'" />
              {{ Math.abs(commodity.change).toFixed(2) }}%
            </span>
          </li>
        </ul>
      </div>
    </div>

    <!-- Bottleneck Overview -->
    <div class="ss-card bottleneck-overview">
      <div class="card-header">
        <h3>{{ t('dashboard.bottleneckStatus') }}</h3>
        <router-link :to="localePath('/bottlenecks')" class="card-link">
          {{ t('dashboard.viewAll') }} <i class="pi pi-arrow-right" />
        </router-link>
      </div>
      <div v-if="loadingBottlenecks" class="card-loading">
        <i class="pi pi-spin pi-spinner" /> {{ t('common.loading') }}
      </div>
      <div v-else-if="bottleneckItems.length === 0" class="card-empty">
        {{ t('common.noData') }}
      </div>
      <div v-else class="bottleneck-grid">
        <div
          v-for="item in bottleneckItems"
          :key="item.id"
          class="bottleneck-item"
        >
          <div class="bottleneck-indicator" :class="`bottleneck-indicator--${item.severity}`" />
          <div class="bottleneck-details">
            <span class="bottleneck-name">{{ item.name }}</span>
            <span class="bottleneck-region text-muted">{{ item.region }}</span>
          </div>
          <span class="ss-badge" :class="`ss-badge--${item.severity}`">
            {{ item.severity }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/useAuthStore'
import { useApi } from '@/composables/useApi'
import { useLocalePath } from '@/composables/useLocalePath'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, CanvasRenderer])

const { t } = useI18n()
const auth = useAuthStore()
const api = useApi()
const { localePath } = useLocalePath()

const userName = computed(() => auth.user?.name?.split(' ')[0] || auth.user?.email || 'User')

const formattedDate = computed(() => {
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(new Date())
})

// KPIs
const kpis = ref({
  activeAlerts: 0,
  vesselsTracked: 0,
  commoditiesMonitored: 0,
  bottleneckRisk: 'Low'
})

const bottleneckRiskClass = computed(() => {
  const risk = kpis.value.bottleneckRisk.toLowerCase()
  if (risk === 'critical') return 'kpi-icon--danger'
  if (risk === 'high') return 'kpi-icon--warning'
  return 'kpi-icon--success'
})

// Alerts
const loadingAlerts = ref(true)
const recentAlerts = ref<any[]>([])

// Prices
const loadingPrices = ref(true)
const topMovers = ref<any[]>([])

// Bottlenecks
const loadingBottlenecks = ref(true)
const bottleneckItems = ref<any[]>([])

// Sparkline charts
const sparklineInstances = new Map<string, echarts.ECharts>()

function registerSparkline(el: HTMLElement | null, symbol: string) {
  if (!el || sparklineInstances.has(symbol)) return
  nextTick(() => {
    const chart = echarts.init(el, undefined, { width: 80, height: 32 })
    const commodity = topMovers.value.find(c => c.symbol === symbol)
    const data = commodity?.sparkline || generateSparkline()
    chart.setOption({
      grid: { top: 0, bottom: 0, left: 0, right: 0 },
      xAxis: { show: false, type: 'category' },
      yAxis: { show: false, type: 'value' },
      series: [{
        type: 'line',
        data,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1.5,
          color: commodity?.change >= 0 ? '#22c55e' : '#ef4444'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: commodity?.change >= 0 ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)' },
            { offset: 1, color: 'rgba(0,0,0,0)' }
          ])
        }
      }]
    })
    sparklineInstances.set(symbol, chart)
  })
}

function generateSparkline(): number[] {
  const points: number[] = []
  let v = 50 + Math.random() * 50
  for (let i = 0; i < 20; i++) {
    v += (Math.random() - 0.5) * 5
    points.push(Math.round(v * 100) / 100)
  }
  return points
}

function severityIcon(severity: string): string {
  if (severity === 'critical') return 'pi pi-times-circle'
  if (severity === 'warning') return 'pi pi-exclamation-circle'
  return 'pi pi-info-circle'
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

// Fetch data
async function fetchDashboard() {
  // Alerts
  try {
    const res: any = await api.get('/alerts', { limit: '5' })
    recentAlerts.value = res.data || []
    kpis.value.activeAlerts = res.total || recentAlerts.value.length
  } catch {
    // Fallback mock data
    recentAlerts.value = [
      { id: 1, title: 'Suez Canal congestion increasing', severity: 'critical', commodity: 'Crude Oil', created_at: new Date(Date.now() - 2 * 3600000).toISOString() },
      { id: 2, title: 'Panama Canal drought restrictions', severity: 'warning', commodity: 'LNG', created_at: new Date(Date.now() - 5 * 3600000).toISOString() },
      { id: 3, title: 'Baltic Dry Index surge +8%', severity: 'info', commodity: 'Iron Ore', created_at: new Date(Date.now() - 12 * 3600000).toISOString() },
      { id: 4, title: 'Ukraine port disruption', severity: 'critical', commodity: 'Wheat', created_at: new Date(Date.now() - 24 * 3600000).toISOString() },
      { id: 5, title: 'LME copper stock drawdown', severity: 'warning', commodity: 'Copper', created_at: new Date(Date.now() - 48 * 3600000).toISOString() },
    ]
    kpis.value.activeAlerts = 12
  }
  loadingAlerts.value = false

  // Prices
  try {
    const res: any = await api.get('/commodities/top-movers')
    topMovers.value = res.data || []
  } catch {
    topMovers.value = [
      { symbol: 'CL', name: 'Crude Oil (WTI)', price: 78.42, change: 2.34, sparkline: generateSparkline() },
      { symbol: 'NG', name: 'Natural Gas', price: 3.15, change: -1.87, sparkline: generateSparkline() },
      { symbol: 'HG', name: 'Copper', price: 4.28, change: 1.56, sparkline: generateSparkline() },
      { symbol: 'ZW', name: 'Wheat', price: 612.50, change: -3.12, sparkline: generateSparkline() },
      { symbol: 'GC', name: 'Gold', price: 2342.80, change: 0.45, sparkline: generateSparkline() },
    ]
  }
  loadingPrices.value = false

  // Bottlenecks
  try {
    const res: any = await api.get('/bottlenecks', { limit: '4' })
    bottleneckItems.value = res.data || []
  } catch {
    bottleneckItems.value = [
      { id: 1, name: 'Suez Canal', region: 'Egypt', severity: 'danger' },
      { id: 2, name: 'Panama Canal', region: 'Central America', severity: 'warning' },
      { id: 3, name: 'Strait of Hormuz', region: 'Middle East', severity: 'warning' },
      { id: 4, name: 'Malacca Strait', region: 'Southeast Asia', severity: 'success' },
    ]
  }
  loadingBottlenecks.value = false

  // KPI fallback
  kpis.value.vesselsTracked = 1247
  kpis.value.commoditiesMonitored = 38
  kpis.value.bottleneckRisk = 'High'
}

onMounted(fetchDashboard)
</script>

<style scoped>
.dashboard-header {
  margin-bottom: 1.5rem;
}

/* KPI cards */
.kpi-card {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--ss-radius);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.kpi-icon--danger {
  background: rgba(239, 68, 68, 0.15);
  color: var(--ss-danger);
}

.kpi-icon--warning {
  background: rgba(245, 158, 11, 0.15);
  color: var(--ss-warning);
}

.kpi-icon--success {
  background: rgba(34, 197, 94, 0.15);
  color: var(--ss-success);
}

.kpi-icon--info {
  background: rgba(59, 130, 246, 0.15);
  color: var(--ss-info);
}

.kpi-icon--accent {
  background: var(--ss-accent-dim);
  color: var(--ss-accent);
}

.kpi-body {
  display: flex;
  flex-direction: column;
}

.kpi-value {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.2;
}

.kpi-label {
  font-size: 0.8rem;
  color: var(--ss-text-muted);
}

/* Dashboard grid */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 1.5rem;
}

@media (max-width: 900px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

/* Card header */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.card-header h3 {
  font-size: 1rem;
  font-weight: 600;
}

.card-link {
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.card-loading,
.card-empty {
  text-align: center;
  padding: 2rem;
  color: var(--ss-text-muted);
  font-size: 0.875rem;
}

/* Alert list */
.alert-list {
  list-style: none;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--ss-border-light);
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-severity {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.alert-severity--critical {
  background: rgba(239, 68, 68, 0.15);
  color: var(--ss-danger);
}

.alert-severity--warning {
  background: rgba(245, 158, 11, 0.15);
  color: var(--ss-warning);
}

.alert-severity--info {
  background: rgba(59, 130, 246, 0.15);
  color: var(--ss-info);
}

.alert-content {
  display: flex;
  flex-direction: column;
}

.alert-title {
  font-size: 0.85rem;
  font-weight: 500;
}

.alert-meta {
  font-size: 0.75rem;
}

/* Mover list */
.mover-list {
  list-style: none;
}

.mover-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--ss-border-light);
}

.mover-item:last-child {
  border-bottom: none;
}

.mover-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.mover-name {
  font-size: 0.85rem;
  font-weight: 500;
}

.mover-price {
  font-size: 0.75rem;
}

.sparkline-chart {
  width: 80px;
  height: 32px;
}

.mover-change {
  font-size: 0.8rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.2rem;
  min-width: 65px;
  justify-content: flex-end;
}

/* Bottleneck overview */
.bottleneck-overview {
  margin-top: 1.5rem;
}

.bottleneck-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.75rem;
}

.bottleneck-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--ss-bg-base);
  border-radius: var(--ss-radius);
}

.bottleneck-indicator {
  width: 4px;
  height: 32px;
  border-radius: 2px;
  flex-shrink: 0;
}

.bottleneck-indicator--danger { background: var(--ss-danger); }
.bottleneck-indicator--warning { background: var(--ss-warning); }
.bottleneck-indicator--success { background: var(--ss-success); }

.bottleneck-details {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.bottleneck-name {
  font-size: 0.85rem;
  font-weight: 500;
}

.bottleneck-region {
  font-size: 0.75rem;
}
</style>
