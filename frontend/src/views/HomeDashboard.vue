<template>
  <div class="view-container fade-in">
    <!-- Header -->
    <div class="dashboard-header">
      <div>
        <h1>{{ t('homeDashboard.title') }}</h1>
        <p class="text-secondary">{{ t('dashboard.title') }}</p>
      </div>
      <DataFreshnessIndicator :last-updated="lastUpdated" />
    </div>

    <!-- Row 1: KPI stat cards -->
    <div class="kpi-grid">
      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--accent">
          <i class="pi pi-chart-line" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">
            <template v-if="dashboard.kpis.topMover">
              {{ dashboard.kpis.topMover.change > 0 ? '+' : '' }}{{ dashboard.kpis.topMover.change.toFixed(2) }}%
            </template>
            <template v-else>--</template>
          </span>
          <span class="kpi-label">{{ t('homeDashboard.topMover') }}</span>
          <span v-if="dashboard.kpis.topMover" class="kpi-sub">{{ formatName(dashboard.kpis.topMover.commodity) }}</span>
        </div>
      </div>

      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--danger">
          <i class="pi pi-bell" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ dashboard.kpis.activeAlerts }}</span>
          <span class="kpi-label">{{ t('dashboard.activeAlerts') }}</span>
        </div>
      </div>

      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--info">
          <i class="pi pi-compass" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ dashboard.kpis.vesselsTracked }}</span>
          <span class="kpi-label">{{ t('dashboard.vesselTracking') }}</span>
        </div>
      </div>

      <div class="ss-card kpi-card">
        <div class="kpi-icon kpi-icon--warn">
          <i class="pi pi-star" />
        </div>
        <div class="kpi-body">
          <span class="kpi-value">{{ watchlist.items.length }}</span>
          <span class="kpi-label">{{ t('homeDashboard.watchlistSummary') }}</span>
        </div>
      </div>
    </div>

    <!-- Row 2: Watchlist sparklines + Recent alerts -->
    <div class="row-2-grid">
      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('homeDashboard.watchlist') }}</h3>
          <router-link :to="localePath('/commodities')" class="view-all-link">{{ t('dashboard.viewAll') }}</router-link>
        </div>
        <LoadingSkeleton v-if="watchlist.loading" variant="table" :rows="4" />
        <EmptyState v-else-if="watchlist.items.length === 0" icon="pi-star" :title="t('homeDashboard.emptyWatchlist')" />
        <div v-else class="watchlist-sparklines">
          <div v-for="item in watchlist.items.slice(0, 6)" :key="item.commodity" class="sparkline-row">
            <span class="sparkline-name">{{ formatName(item.commodity) }}</span>
            <span class="sparkline-price">${{ item.price?.toFixed(2) ?? '--' }}</span>
            <span class="sparkline-change" :class="(item.change_24h ?? 0) >= 0 ? 'up' : 'down'">
              {{ (item.change_24h ?? 0) >= 0 ? '+' : '' }}{{ (item.change_24h ?? 0).toFixed(2) }}%
            </span>
            <svg class="sparkline-svg" viewBox="0 0 60 20" preserveAspectRatio="none">
              <polyline
                :points="sparklinePoints(item.sparkline_7d)"
                fill="none"
                :stroke="(item.change_24h ?? 0) >= 0 ? '#22c55e' : '#ef4444'"
                stroke-width="1.5"
              />
            </svg>
          </div>
        </div>
      </div>

      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('dashboard.recentAlerts') }}</h3>
          <router-link :to="localePath('/alerts')" class="view-all-link">{{ t('dashboard.viewAll') }}</router-link>
        </div>
        <LoadingSkeleton v-if="dashboard.loading" variant="table" :rows="5" />
        <EmptyState v-else-if="dashboard.recentAlerts.length === 0" icon="pi-bell" :title="t('alerts.noAlerts')" />
        <div v-else class="alert-list">
          <div v-for="alert in dashboard.recentAlerts.slice(0, 5)" :key="alert.id" class="alert-row">
            <span class="alert-severity-dot" :class="`dot-${alert.severity}`" />
            <div class="alert-content">
              <span class="alert-title-text">{{ alert.title }}</span>
              <span class="alert-meta">{{ alert.type }} &middot; {{ formatTime(alert.time) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Row 3: Active voyages donut + News feed -->
    <div class="row-2-grid">
      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('homeDashboard.activeVoyages') }}</h3>
        </div>
        <div class="voyages-placeholder">
          <div class="donut-chart">
            <svg viewBox="0 0 100 100" class="donut-svg">
              <circle cx="50" cy="50" r="40" fill="none" stroke="var(--ss-border-light)" stroke-width="12" />
              <circle cx="50" cy="50" r="40" fill="none" stroke="var(--ss-accent)" stroke-width="12"
                stroke-dasharray="175 251" stroke-dashoffset="0" transform="rotate(-90 50 50)" />
            </svg>
            <div class="donut-center">
              <span class="donut-value">{{ dashboard.kpis.vesselsTracked || '--' }}</span>
              <span class="donut-label">{{ t('map.vessels') }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('homeDashboard.newsFeed') }}</h3>
        </div>
        <EmptyState icon="pi-globe" :title="t('common.comingSoon')" :description="t('homeDashboard.newsComingSoon')" />
      </div>
    </div>

    <!-- Row 4: Market Heatmap -->
    <div class="ss-card">
      <MarketHeatmap :data="dashboard.heatmapData" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLocalePath } from '@/composables/useLocalePath'
import { useDashboardStore } from '@/stores/useDashboardStore'
import { useWatchlistStore } from '@/stores/useWatchlistStore'
import MarketHeatmap from '@/components/dashboard/MarketHeatmap.vue'
import LoadingSkeleton from '@/components/ui/LoadingSkeleton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import DataFreshnessIndicator from '@/components/ui/DataFreshnessIndicator.vue'

const { t } = useI18n()
const { localePath } = useLocalePath()
const dashboard = useDashboardStore()
const watchlist = useWatchlistStore()
const lastUpdated = ref<string | null>(null)

onMounted(async () => {
  await Promise.all([dashboard.fetchDashboard(), watchlist.fetchWatchlist()])
  lastUpdated.value = new Date().toISOString()
})

function formatName(name: string) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('alerts.justNow')
  if (mins < 60) return t('alerts.minutesAgo', { n: mins })
  const hours = Math.floor(mins / 60)
  if (hours < 24) return t('alerts.hoursAgo', { n: hours })
  return t('alerts.daysAgo', { n: Math.floor(hours / 24) })
}

function sparklinePoints(data: number[]) {
  if (!data || data.length < 2) return '0,10 60,10'
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  return data.map((v, i) => {
    const x = (i / (data.length - 1)) * 60
    const y = 18 - ((v - min) / range) * 16
    return `${x},${y}`
  }).join(' ')
}
</script>

<style scoped>
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.dashboard-header h1 {
  font-size: 1.5rem;
  margin: 0;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
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

.kpi-icon--accent { background: rgba(59, 130, 246, 0.15); color: var(--ss-accent); }
.kpi-icon--danger { background: rgba(239, 68, 68, 0.15); color: var(--ss-danger); }
.kpi-icon--info { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.kpi-icon--warn { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }

.kpi-body {
  display: flex;
  flex-direction: column;
}

.kpi-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--ss-text-primary);
  line-height: 1.2;
}

.kpi-label {
  font-size: 0.8rem;
  color: var(--ss-text-muted);
}

.kpi-sub {
  font-size: 0.7rem;
  color: var(--ss-text-secondary);
  text-transform: capitalize;
}

.row-2-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem 0.75rem;
}

.card-header h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.view-all-link {
  font-size: 0.8rem;
  color: var(--ss-accent);
  text-decoration: none;
}

.view-all-link:hover { text-decoration: underline; }

/* Watchlist sparklines */
.watchlist-sparklines {
  padding: 0 1.25rem 1rem;
}

.sparkline-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--ss-border-light);
}

.sparkline-row:last-child { border-bottom: none; }

.sparkline-name {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--ss-text-primary);
  text-transform: capitalize;
}

.sparkline-price {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ss-text-primary);
  min-width: 60px;
  text-align: right;
}

.sparkline-change {
  font-size: 0.8rem;
  font-weight: 600;
  min-width: 55px;
  text-align: right;
}

.sparkline-change.up { color: #22c55e; }
.sparkline-change.down { color: #ef4444; }

.sparkline-svg {
  width: 60px;
  height: 20px;
  flex-shrink: 0;
}

/* Alert list */
.alert-list {
  padding: 0 1.25rem 1rem;
}

.alert-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--ss-border-light);
}

.alert-row:last-child { border-bottom: none; }

.alert-severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 0.35rem;
  flex-shrink: 0;
}

.dot-critical { background: #ef4444; }
.dot-warning { background: #f59e0b; }
.dot-info { background: #3b82f6; }

.alert-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.alert-title-text {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--ss-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-meta {
  font-size: 0.75rem;
  color: var(--ss-text-muted);
}

/* Donut */
.voyages-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.donut-chart {
  position: relative;
  width: 140px;
  height: 140px;
}

.donut-svg {
  width: 100%;
  height: 100%;
}

.donut-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.donut-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--ss-text-primary);
}

.donut-label {
  font-size: 0.7rem;
  color: var(--ss-text-muted);
}

@media (max-width: 1024px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 768px) {
  .kpi-grid { grid-template-columns: 1fr; }
  .row-2-grid { grid-template-columns: 1fr; }
}
</style>
