<template>
  <div class="alerts-view">
    <!-- Top Bar -->
    <header class="alerts-header">
      <div class="header-left">
        <h1>{{ t('alerts.title') }}</h1>
        <span class="alert-total-badge">{{ filteredAlerts.length }}</span>
      </div>
      <div class="header-right">
        <span class="last-refresh" v-if="lastRefreshAt">
          {{ t('common.lastUpdated') }}: {{ formatRelativeTime(lastRefreshAt) }}
        </span>
        <button class="refresh-btn" @click="fetchAlerts" :disabled="loading" :title="t('common.retry')">
          <i class="pi pi-refresh" :class="{ 'spin': loading }" />
        </button>
      </div>
    </header>

    <!-- Filters Row -->
    <div class="filters-row">
      <div class="filter-group">
        <label class="filter-label">{{ t('alerts.severity') }}</label>
        <div class="severity-toggles">
          <button
            v-for="s in severityOptions"
            :key="s.value"
            :class="['sev-btn', `sev-${s.value}`, { active: severityFilter === s.value }]"
            @click="severityFilter = severityFilter === s.value ? 'all' : s.value"
          >
            <span v-if="s.value !== 'all'" class="sev-dot" :class="`dot-${s.value}`" />
            {{ s.label }}
            <span v-if="s.value !== 'all'" class="sev-count">{{ countBySeverity(s.value) }}</span>
          </button>
        </div>
      </div>

      <div class="filter-group">
        <label class="filter-label">{{ t('alerts.type') }}</label>
        <select v-model="typeFilter" class="filter-select">
          <option value="all">{{ t('alerts.allTypes') }}</option>
          <option v-for="tp in alertTypes" :key="tp.value" :value="tp.value">{{ tp.label }}</option>
        </select>
      </div>

      <div class="filter-group">
        <label class="filter-label">{{ t('alerts.commodity') }}</label>
        <select v-model="commodityFilter" class="filter-select">
          <option value="all">{{ t('alerts.allCommodities') }}</option>
          <option v-for="c in availableCommodities" :key="c" :value="c">{{ formatCommodityName(c) }}</option>
        </select>
      </div>

      <div class="filter-group">
        <label class="filter-label">{{ t('alerts.timeRange') }}</label>
        <div class="time-toggles">
          <button
            v-for="tr in timeRangeOptions"
            :key="tr.value"
            :class="['time-btn', { active: timeRange === tr.value }]"
            @click="timeRange = tr.value"
          >
            {{ tr.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="alerts-content">
      <!-- Alerts List -->
      <div class="alerts-list-panel">
        <!-- Loading State -->
        <div v-if="loading && !alerts.length" class="skeleton-list">
          <div v-for="i in 6" :key="i" class="skeleton-card">
            <div class="skeleton-bar skeleton-title" />
            <div class="skeleton-bar skeleton-body" />
            <div class="skeleton-bar skeleton-meta" />
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="!filteredAlerts.length" class="empty-state">
          <i class="pi pi-bell-slash empty-icon" />
          <h3>{{ t('alerts.noAlertsTitle') }}</h3>
          <p>{{ t('alerts.noAlertsDesc') }}</p>
        </div>

        <!-- Alert Cards -->
        <TransitionGroup name="alert-list" tag="div" class="alert-cards" v-else>
          <div
            v-for="alert in paginatedAlerts"
            :key="alert.id"
            :class="['alert-card', `border-${alert.severity}`]"
            @click="selectedAlert = selectedAlert?.id === alert.id ? null : alert"
          >
            <div class="alert-card-top">
              <div class="alert-icon-wrap" :class="`icon-${alert.severity}`">
                <i :class="['pi', alertTypeIcon(alert.type)]" />
              </div>
              <div class="alert-card-main">
                <div class="alert-card-header">
                  <span class="alert-title">{{ alert.title }}</span>
                  <span :class="['severity-tag', `tag-${alert.severity}`]">
                    {{ t(`alerts.${alert.severity}`) }}
                  </span>
                </div>
                <p class="alert-body" :class="{ expanded: selectedAlert?.id === alert.id }">
                  {{ alert.body }}
                </p>
                <div class="alert-meta">
                  <span class="meta-tags">
                    <span v-if="alert.commodity" class="meta-tag tag-commodity">
                      {{ formatCommodityName(alert.commodity) }}
                    </span>
                    <span v-if="alert.region" class="meta-tag tag-region">
                      {{ alert.region }}
                    </span>
                    <span class="meta-tag tag-type">
                      {{ alertTypeLabel(alert.type) }}
                    </span>
                  </span>
                  <span class="alert-time">{{ formatRelativeTime(alert.created_at) }}</span>
                </div>
                <a
                  v-if="selectedAlert?.id === alert.id && alert.source_url"
                  :href="alert.source_url"
                  target="_blank"
                  rel="noopener"
                  class="source-link"
                >
                  <i class="pi pi-external-link" /> {{ t('alerts.viewSource') }}
                </a>
              </div>
            </div>
          </div>
        </TransitionGroup>

        <!-- Pagination -->
        <div v-if="filteredAlerts.length > pageSize" class="pagination">
          <button
            class="page-btn"
            :disabled="currentPage === 1"
            @click="currentPage--"
          >
            <i class="pi pi-chevron-left" />
          </button>
          <span class="page-info">
            {{ currentPage }} / {{ totalPages }}
          </span>
          <button
            class="page-btn"
            :disabled="currentPage === totalPages"
            @click="currentPage++"
          >
            <i class="pi pi-chevron-right" />
          </button>
        </div>
      </div>

      <!-- Stats Panel -->
      <aside class="stats-panel">
        <!-- Severity Summary -->
        <div class="stats-card">
          <h3 class="stats-title">{{ t('alerts.severitySummary') }}</h3>
          <div class="severity-bars">
            <div class="sev-row" v-for="s in ['critical', 'warning', 'info']" :key="s">
              <div class="sev-row-label">
                <span class="sev-indicator" :class="`ind-${s}`" />
                <span>{{ t(`alerts.${s}`) }}</span>
              </div>
              <div class="sev-bar-track">
                <div
                  class="sev-bar-fill"
                  :class="`fill-${s}`"
                  :style="{ width: sevBarWidth(s) }"
                />
              </div>
              <span class="sev-row-count">{{ countBySeverity(s) }}</span>
            </div>
          </div>
        </div>

        <!-- Trend Chart -->
        <div class="stats-card">
          <h3 class="stats-title">{{ t('alerts.trend24h') }}</h3>
          <div ref="trendChartRef" class="trend-chart" />
        </div>

        <!-- Top Affected -->
        <div class="stats-card">
          <h3 class="stats-title">{{ t('alerts.topAffected') }}</h3>
          <div v-if="topCommodities.length" class="top-list">
            <div v-for="item in topCommodities" :key="item.name" class="top-item">
              <span class="top-name">{{ formatCommodityName(item.name) }}</span>
              <span class="top-count-bar">
                <span class="top-bar" :style="{ width: `${(item.count / topCommodities[0].count) * 100}%` }" />
              </span>
              <span class="top-count">{{ item.count }}</span>
            </div>
          </div>
          <div v-else class="top-empty">{{ t('common.noData') }}</div>
        </div>

        <!-- Top Regions -->
        <div class="stats-card">
          <h3 class="stats-title">{{ t('alerts.topRegions') }}</h3>
          <div v-if="topRegions.length" class="top-list">
            <div v-for="item in topRegions" :key="item.name" class="top-item">
              <span class="top-name">{{ item.name }}</span>
              <span class="top-count-bar">
                <span class="top-bar bar-region" :style="{ width: `${(item.count / topRegions[0].count) * 100}%` }" />
              </span>
              <span class="top-count">{{ item.count }}</span>
            </div>
          </div>
          <div v-else class="top-empty">{{ t('common.noData') }}</div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useApi } from '@/composables/useApi'
import { useChart } from '@/composables/useChart'

const { t } = useI18n()
const api = useApi()

// ---------- Types ----------
interface Alert {
  id: string
  severity: 'critical' | 'warning' | 'info'
  type: string
  title: string
  body: string
  commodity: string | null
  region: string | null
  source_url: string | null
  created_at: string
}

interface AlertsResponse {
  data: Alert[]
  total: number
}

// ---------- State ----------
const alerts = ref<Alert[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const lastRefreshAt = ref<string | null>(null)
const selectedAlert = ref<Alert | null>(null)

// Filters
const severityFilter = ref<string>('all')
const typeFilter = ref<string>('all')
const commodityFilter = ref<string>('all')
const timeRange = ref<string>('24h')

// Pagination
const currentPage = ref(1)
const pageSize = 20

// Chart
const trendChartRef = ref<HTMLElement | null>(null)
const { setOption } = useChart(trendChartRef)

// ---------- Filter Options ----------
const severityOptions = computed(() => [
  { value: 'all', label: t('alerts.all') },
  { value: 'critical', label: t('alerts.critical') },
  { value: 'warning', label: t('alerts.warning') },
  { value: 'info', label: t('alerts.info') },
])

const alertTypes = [
  { value: 'ais_anomaly', label: 'AIS Anomaly' },
  { value: 'price_move', label: 'Price Move' },
  { value: 'news', label: 'News' },
  { value: 'port_congestion', label: 'Port Congestion' },
  { value: 'geopolitical', label: 'Geopolitical' },
]

const timeRangeOptions = [
  { value: '1h', label: '1H' },
  { value: '6h', label: '6H' },
  { value: '24h', label: '24H' },
  { value: '7d', label: '7D' },
]

// ---------- Computed ----------
const availableCommodities = computed(() => {
  const set = new Set<string>()
  alerts.value.forEach(a => { if (a.commodity) set.add(a.commodity) })
  return Array.from(set).sort()
})

const timeRangeMs = computed(() => {
  const map: Record<string, number> = {
    '1h': 3600000,
    '6h': 21600000,
    '24h': 86400000,
    '7d': 604800000,
  }
  return map[timeRange.value] || 86400000
})

const filteredAlerts = computed(() => {
  const now = Date.now()
  const cutoff = now - timeRangeMs.value

  return alerts.value.filter(a => {
    if (severityFilter.value !== 'all' && a.severity !== severityFilter.value) return false
    if (typeFilter.value !== 'all' && a.type !== typeFilter.value) return false
    if (commodityFilter.value !== 'all' && a.commodity !== commodityFilter.value) return false
    if (new Date(a.created_at).getTime() < cutoff) return false
    return true
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredAlerts.value.length / pageSize)))

const paginatedAlerts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredAlerts.value.slice(start, start + pageSize)
})

const topCommodities = computed(() => {
  const map = new Map<string, number>()
  filteredAlerts.value.forEach(a => {
    if (a.commodity) map.set(a.commodity, (map.get(a.commodity) || 0) + 1)
  })
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
})

const topRegions = computed(() => {
  const map = new Map<string, number>()
  filteredAlerts.value.forEach(a => {
    if (a.region) map.set(a.region, (map.get(a.region) || 0) + 1)
  })
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
})

// ---------- Functions ----------
function countBySeverity(sev: string): number {
  const now = Date.now()
  const cutoff = now - timeRangeMs.value
  return alerts.value.filter(a =>
    a.severity === sev && new Date(a.created_at).getTime() >= cutoff
  ).length
}

function sevBarWidth(sev: string): string {
  const total = filteredAlerts.value.length || 1
  return `${Math.round((countBySeverity(sev) / total) * 100)}%`
}

function alertTypeIcon(type: string): string {
  const map: Record<string, string> = {
    ais_anomaly: 'pi-compass',
    price_move: 'pi-chart-line',
    news: 'pi-megaphone',
    port_congestion: 'pi-warehouse',
    geopolitical: 'pi-globe',
  }
  return map[type] || 'pi-bell'
}

function alertTypeLabel(type: string): string {
  return alertTypes.find(t => t.value === type)?.label || type.replace(/_/g, ' ')
}

function formatCommodityName(commodity: string): string {
  return commodity.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return t('alerts.justNow')
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return t('alerts.minutesAgo', { n: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('alerts.hoursAgo', { n: hours })
  const days = Math.floor(hours / 24)
  return t('alerts.daysAgo', { n: days })
}

function buildTrendChart() {
  const now = Date.now()
  const hours = 24
  const bins = new Array(hours).fill(0)
  const labels: string[] = []

  for (let i = 0; i < hours; i++) {
    const hourStart = now - (hours - i) * 3600000
    const hourEnd = hourStart + 3600000
    const label = new Date(hourStart).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    labels.push(label)
    bins[i] = alerts.value.filter(a => {
      const t = new Date(a.created_at).getTime()
      return t >= hourStart && t < hourEnd
    }).length
  }

  setOption({
    grid: { left: 35, right: 10, top: 10, bottom: 30 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        fontSize: 10,
        interval: 5,
        rotate: 0,
      },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { fontSize: 10 },
    },
    tooltip: {
      trigger: 'axis',
    },
    series: [
      {
        type: 'bar',
        data: bins,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#3b82f6' },
              { offset: 1, color: '#1d4ed8' },
            ],
          },
          borderRadius: [3, 3, 0, 0],
        },
        barMaxWidth: 16,
      },
    ],
  })
}

async function fetchAlerts() {
  loading.value = true
  error.value = null

  try {
    const params: Record<string, string> = {
      limit: '200',
      offset: '0',
    }
    if (severityFilter.value !== 'all') params.severity = severityFilter.value

    const res = await api.get<AlertsResponse>('/alerts', params)
    alerts.value = res.data
    lastRefreshAt.value = new Date().toISOString()
    await nextTick()
    buildTrendChart()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch alerts'
    console.error('Failed to fetch alerts:', e)
  } finally {
    loading.value = false
  }
}

// Reset page on filter change
watch([severityFilter, typeFilter, commodityFilter, timeRange], () => {
  currentPage.value = 1
})

// Auto-refresh
let refreshInterval: ReturnType<typeof setInterval>

onMounted(() => {
  fetchAlerts()
  refreshInterval = setInterval(fetchAlerts, 60000)
})

onUnmounted(() => {
  clearInterval(refreshInterval)
})
</script>

<style scoped>
.alerts-view {
  padding: 1.5rem 2rem;
  max-width: 1600px;
  margin: 0 auto;
  color: #f1f5f9;
  min-height: 100vh;
}

/* ---- Header ---- */
.alerts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-left h1 {
  font-size: 1.75rem;
  margin: 0;
  font-weight: 700;
}

.alert-total-badge {
  background: #3b82f6;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  min-width: 28px;
  text-align: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.last-refresh {
  color: #64748b;
  font-size: 0.8rem;
}

.refresh-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.refresh-btn:hover {
  border-color: #3b82f6;
  color: #e2e8f0;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ---- Filters ---- */
.filters-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  padding: 1rem 1.25rem;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 12px;
  margin-bottom: 1.5rem;
  align-items: flex-end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.filter-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  font-weight: 600;
}

.severity-toggles,
.time-toggles {
  display: flex;
  gap: 0.25rem;
}

.sev-btn,
.time-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  transition: all 0.2s;
  white-space: nowrap;
}

.sev-btn:hover,
.time-btn:hover {
  border-color: #475569;
  color: #e2e8f0;
}

.sev-btn.active,
.time-btn.active {
  background: #334155;
  border-color: #475569;
  color: #fff;
}

.sev-btn.sev-critical.active { background: #7f1d1d; border-color: #dc2626; }
.sev-btn.sev-warning.active { background: #78350f; border-color: #f59e0b; }
.sev-btn.sev-info.active { background: #1e3a5f; border-color: #3b82f6; }

.sev-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-critical { background: #ef4444; }
.dot-warning { background: #f59e0b; }
.dot-info { background: #3b82f6; }

.sev-count {
  background: rgba(255,255,255,0.1);
  padding: 0 0.35rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
}

.filter-select {
  background: #1e293b;
  border: 1px solid #334155;
  color: #e2e8f0;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  min-width: 140px;
  outline: none;
  transition: border-color 0.2s;
}

.filter-select:focus {
  border-color: #3b82f6;
}

.filter-select option {
  background: #1e293b;
  color: #e2e8f0;
}

/* ---- Content Layout ---- */
.alerts-content {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 1.5rem;
  align-items: start;
}

/* ---- Alert Cards ---- */
.alerts-list-panel {
  min-height: 400px;
}

.alert-cards {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.alert-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-left: 4px solid #334155;
  border-radius: 10px;
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.alert-card:hover {
  border-color: #475569;
  background: #1e293b;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.alert-card.border-critical { border-left-color: #ef4444; }
.alert-card.border-warning { border-left-color: #f59e0b; }
.alert-card.border-info { border-left-color: #3b82f6; }

.alert-card-top {
  display: flex;
  gap: 0.85rem;
}

.alert-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 0.95rem;
}

.icon-critical { background: rgba(239,68,68,0.15); color: #ef4444; }
.icon-warning { background: rgba(245,158,11,0.15); color: #f59e0b; }
.icon-info { background: rgba(59,130,246,0.15); color: #3b82f6; }

.alert-card-main {
  flex: 1;
  min-width: 0;
}

.alert-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.alert-title {
  font-weight: 600;
  font-size: 0.95rem;
  line-height: 1.3;
}

.severity-tag {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
  letter-spacing: 0.03em;
}

.tag-critical { background: #7f1d1d; color: #fca5a5; }
.tag-warning { background: #78350f; color: #fcd34d; }
.tag-info { background: #1e3a5f; color: #93c5fd; }

.alert-body {
  color: #94a3b8;
  font-size: 0.85rem;
  line-height: 1.5;
  margin: 0 0 0.5rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.alert-body.expanded {
  -webkit-line-clamp: unset;
  overflow: visible;
}

.alert-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.meta-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.meta-tag {
  font-size: 0.7rem;
  padding: 2px 7px;
  border-radius: 4px;
  background: #334155;
  color: #94a3b8;
  white-space: nowrap;
}

.tag-commodity { background: #1a2332; color: #7dd3fc; }
.tag-region { background: #1f2a1a; color: #86efac; }
.tag-type { background: #2a1f33; color: #c4b5fd; }

.alert-time {
  color: #64748b;
  font-size: 0.75rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: #3b82f6;
  text-decoration: none;
  transition: color 0.2s;
}

.source-link:hover {
  color: #60a5fa;
}

/* ---- Pagination ---- */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
  padding: 0.75rem 0;
}

.page-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #e2e8f0;
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-info {
  color: #64748b;
  font-size: 0.85rem;
}

/* ---- Stats Panel ---- */
.stats-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stats-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.25rem;
}

.stats-title {
  font-size: 0.85rem;
  font-weight: 600;
  margin: 0 0 1rem;
  color: #e2e8f0;
}

/* Severity Bars */
.severity-bars {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.sev-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.sev-row-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: #94a3b8;
  min-width: 80px;
}

.sev-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ind-critical { background: #ef4444; }
.ind-warning { background: #f59e0b; }
.ind-info { background: #3b82f6; }

.sev-bar-track {
  flex: 1;
  height: 6px;
  background: #0f172a;
  border-radius: 3px;
  overflow: hidden;
}

.sev-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.fill-critical { background: #ef4444; }
.fill-warning { background: #f59e0b; }
.fill-info { background: #3b82f6; }

.sev-row-count {
  font-size: 0.85rem;
  font-weight: 700;
  color: #e2e8f0;
  min-width: 28px;
  text-align: right;
}

/* Trend Chart */
.trend-chart {
  height: 160px;
}

/* Top Lists */
.top-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.top-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.top-name {
  font-size: 0.8rem;
  color: #cbd5e1;
  min-width: 90px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.top-count-bar {
  flex: 1;
  height: 6px;
  background: #0f172a;
  border-radius: 3px;
  overflow: hidden;
}

.top-bar {
  height: 100%;
  background: #3b82f6;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.top-bar.bar-region {
  background: #10b981;
}

.top-count {
  font-size: 0.8rem;
  font-weight: 700;
  color: #e2e8f0;
  min-width: 24px;
  text-align: right;
}

.top-empty {
  color: #475569;
  font-size: 0.8rem;
  text-align: center;
  padding: 1rem 0;
}

/* ---- Skeleton / Loading ---- */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.skeleton-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 1.25rem;
}

.skeleton-bar {
  background: linear-gradient(90deg, #334155 25%, #3d4f66 50%, #334155 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.skeleton-title {
  width: 65%;
  height: 16px;
  margin-bottom: 0.75rem;
}

.skeleton-body {
  width: 90%;
  height: 12px;
  margin-bottom: 0.5rem;
}

.skeleton-meta {
  width: 40%;
  height: 10px;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

/* ---- Empty State ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 3rem;
  color: #334155;
  margin-bottom: 1rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
  color: #94a3b8;
}

.empty-state p {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
  max-width: 360px;
}

/* ---- Transitions ---- */
.alert-list-enter-active,
.alert-list-leave-active {
  transition: all 0.3s ease;
}

.alert-list-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.alert-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* ---- Responsive ---- */
@media (max-width: 1024px) {
  .alerts-content {
    grid-template-columns: 1fr;
  }

  .stats-panel {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
}

@media (max-width: 768px) {
  .alerts-view {
    padding: 1rem;
  }

  .alerts-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .filters-row {
    flex-direction: column;
    gap: 0.75rem;
  }

  .severity-toggles {
    flex-wrap: wrap;
  }

  .filter-select {
    width: 100%;
  }

  .time-toggles {
    flex-wrap: wrap;
  }

  .stats-panel {
    grid-template-columns: 1fr;
  }

  .alert-meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
