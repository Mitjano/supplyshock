<template>
  <div class="right-panel" :class="{ collapsed: isCollapsed }">
    <button class="toggle-btn" @click="isCollapsed = !isCollapsed">
      {{ isCollapsed ? '\u25C0' : '\u25B6' }}
    </button>

    <div v-if="!isCollapsed" class="panel-content">
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
          @click="switchTab(tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Chokepoints tab -->
      <div v-if="activeTab === 'chokepoints'" class="tab-content">
        <div v-if="chokepointsLoading" class="loading-state">
          <div class="mini-spinner"></div>
          <span>{{ t('map.loadingBottlenecks') }}</span>
        </div>
        <div v-else-if="chokepointsError" class="error-state">
          <i class="pi pi-exclamation-circle"></i>
          <span>{{ t('map.errorBottlenecks') }}</span>
          <button class="retry-btn" @click="loadBottlenecks">{{ t('common.retry') }}</button>
        </div>
        <template v-else>
          <div v-for="node in chokepoints" :key="node.slug" class="item-card">
            <div class="item-header">
              <span class="item-name">{{ node.name }}</span>
              <span class="risk-badge" :class="riskClass(node.risk)">{{ node.risk }}</span>
            </div>
            <div class="item-meta">
              {{ node.type }} &middot; {{ node.country }}
              <span v-if="node.vessel_count" class="vessel-count">{{ node.vessel_count }} {{ t('map.vessels').toLowerCase() }}</span>
            </div>
          </div>
          <div v-if="!chokepoints.length" class="empty-state">{{ t('common.noData') }}</div>
        </template>
      </div>

      <!-- Alerts tab -->
      <div v-if="activeTab === 'alerts'" class="tab-content">
        <div v-if="alertsLoading" class="loading-state">
          <div class="mini-spinner"></div>
          <span>{{ t('map.loadingAlerts') }}</span>
        </div>
        <div v-else-if="alertsError" class="error-state">
          <i class="pi pi-exclamation-circle"></i>
          <span>{{ t('map.errorAlerts') }}</span>
          <button class="retry-btn" @click="loadAlerts">{{ t('common.retry') }}</button>
        </div>
        <template v-else>
          <div v-for="alert in alerts" :key="alert.id" class="item-card">
            <div class="item-header">
              <span class="item-name">{{ alert.title }}</span>
              <span class="severity-badge" :class="alert.severity">{{ alert.severity }}</span>
            </div>
            <div class="item-meta">{{ formatTime(alert.created_at) }}</div>
          </div>
          <div v-if="!alerts.length" class="empty-state">{{ t('map.noAlerts') }}</div>
        </template>
      </div>

      <!-- Voyages tab -->
      <div v-if="activeTab === 'voyages'" class="tab-content">
        <div v-if="voyagesLoading" class="loading-state">
          <div class="mini-spinner"></div>
          <span>{{ t('map.loadingVoyages') }}</span>
        </div>
        <div v-else-if="voyagesError" class="error-state">
          <i class="pi pi-exclamation-circle"></i>
          <span>{{ t('map.errorVoyages') }}</span>
          <button class="retry-btn" @click="loadVoyages">{{ t('common.retry') }}</button>
        </div>
        <template v-else>
          <div v-for="voyage in voyageList" :key="voyage.id" class="item-card">
            <div class="item-header">
              <span class="item-name">{{ voyage.vessel_name || 'MMSI ' + voyage.mmsi }}</span>
              <span class="laden-badge" :class="voyage.laden_status || 'unknown'">
                {{ voyage.laden_status === 'laden' ? t('map.laden') : voyage.laden_status === 'ballast' ? t('map.ballast') : t('map.unknown') }}
              </span>
            </div>
            <div class="voyage-route-row">
              <span>{{ voyage.origin?.name || '?' }}</span>
              <span class="arrow">&rarr;</span>
              <span>{{ voyage.destination?.name || t('map.enRoute') }}</span>
            </div>
            <div class="item-meta">
              {{ formatVesselType(voyage.vessel_type) }}
              <span v-if="voyage.cargo_type" class="cargo-tag">{{ formatCommodity(voyage.cargo_type) }}</span>
              <span v-if="voyage.volume_estimate" class="volume-tag">{{ formatVolume(voyage.volume_estimate) }} MT</span>
            </div>
          </div>
          <div v-if="!voyageList.length" class="empty-state">{{ t('map.noVoyages') }}</div>
        </template>
      </div>

      <!-- Flows tab -->
      <div v-if="activeTab === 'flows'" class="tab-content">
        <table class="flows-table">
          <thead>
            <tr>
              <th>{{ t('map.route') }}</th>
              <th>{{ t('map.commodity') }}</th>
              <th>{{ t('map.volume') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(flow, i) in topFlows" :key="i">
              <td>{{ flow.origin }} &rarr; {{ flow.destination }}</td>
              <td>
                <span class="commodity-dot" :style="{ background: commodityColor(flow.commodity) }"></span>
                {{ formatCommodity(flow.commodity) }}
              </td>
              <td>{{ formatVolume(flow.volume_mt) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!topFlows.length" class="empty-state">{{ t('common.noData') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMapStore } from '../../stores/useMapStore'

const { t } = useI18n()
const mapStore = useMapStore()
const isCollapsed = ref(false)
const activeTab = ref('chokepoints')

const chokepointsLoading = ref(false)
const chokepointsError = ref(false)
const alertsLoading = ref(false)
const alertsError = ref(false)

const voyagesLoading = ref(false)
const voyagesError = ref(false)

const tabs = computed(() => [
  { id: 'chokepoints', label: t('map.chokepoints') },
  { id: 'alerts', label: t('map.alerts') },
  { id: 'flows', label: t('map.flows') },
  { id: 'voyages', label: t('map.voyages') },
])

// Real data from store
const chokepoints = computed(() => mapStore.bottlenecks)
const alerts = computed(() => mapStore.alerts)

const topFlows = computed(() => {
  return mapStore.tradeFlows.slice(0, 6).map(f => ({
    origin: f.properties.origin,
    destination: f.properties.destination,
    commodity: f.properties.commodity,
    volume_mt: f.properties.volume_mt,
  }))
})

const COMMODITY_COLORS: Record<string, string> = {
  crude_oil: '#ef4444',
  coal: '#374151',
  iron_ore: '#b45309',
  copper: '#d97706',
  lng: '#10b981',
}

function commodityColor(c: string) { return COMMODITY_COLORS[c] || '#6b7280' }
function formatCommodity(c: string) { return c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }
function formatVesselType(t: string) { return t.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }

const voyageList = computed(() => {
  return mapStore.underwayVoyages.slice(0, 20)
})
function formatVolume(v: number | null) { return v ? `${(v / 1000).toFixed(0)}k MT` : '\u2014' }
function riskClass(risk: number) { return risk >= 8 ? 'high' : risk >= 5 ? 'medium' : 'low' }

function formatTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return t('alerts.justNow')
  if (minutes < 60) return t('alerts.minutesAgo', { n: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('alerts.hoursAgo', { n: hours })
  return t('alerts.daysAgo', { n: Math.floor(hours / 24) })
}

async function loadBottlenecks() {
  chokepointsLoading.value = true
  chokepointsError.value = false
  try {
    await mapStore.fetchBottlenecks()
  } catch {
    chokepointsError.value = true
  } finally {
    chokepointsLoading.value = false
  }
}

async function loadAlerts() {
  alertsLoading.value = true
  alertsError.value = false
  try {
    await mapStore.fetchAlerts(10)
  } catch {
    alertsError.value = true
  } finally {
    alertsLoading.value = false
  }
}

function switchTab(id: string) {
  activeTab.value = id
  // Lazy-load tab data on first visit
  if (id === 'chokepoints' && !chokepoints.value.length && !chokepointsLoading.value) {
    loadBottlenecks()
  }
  if (id === 'alerts' && !alerts.value.length && !alertsLoading.value) {
    loadAlerts()
  }
  if (id === 'voyages' && !mapStore.voyages.length && !voyagesLoading.value) {
    loadVoyages()
  }
}

async function loadVoyages() {
  voyagesLoading.value = true
  voyagesError.value = false
  try {
    await mapStore.fetchVoyages({ status: 'underway' })
  } catch {
    voyagesError.value = true
  } finally {
    voyagesLoading.value = false
  }
}

onMounted(() => {
  // Load chokepoints on mount since it's the default tab
  loadBottlenecks()
})
</script>

<style scoped>
.right-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 320px;
  height: 100%;
  background: rgba(15, 23, 42, 0.95);
  border-left: 1px solid #1e293b;
  z-index: 20;
  transition: width 0.2s;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(8px);
}

.right-panel.collapsed {
  width: 0;
  overflow: hidden;
}

.toggle-btn {
  position: absolute;
  left: -28px;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid #334155;
  border-right: none;
  border-radius: 6px 0 0 6px;
  color: #94a3b8;
  padding: 0.5rem 0.25rem;
  cursor: pointer;
  font-size: 0.75rem;
}

.panel-content {
  overflow-y: auto;
  flex: 1;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #1e293b;
}

.tab-btn {
  flex: 1;
  padding: 0.75rem 0.5rem;
  background: none;
  border: none;
  color: #64748b;
  font-size: 0.8rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
  color: #94a3b8;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab-content {
  padding: 0.75rem;
}

/* Loading & error states */
.loading-state {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1.5rem;
  color: #64748b;
  font-size: 0.85rem;
}

.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1.5rem;
  color: #f87171;
  font-size: 0.85rem;
  text-align: center;
}

.error-state i {
  font-size: 1.5rem;
}

.retry-btn {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  color: #60a5fa;
  padding: 0.4rem 1rem;
  font-size: 0.8rem;
  cursor: pointer;
  margin-top: 0.25rem;
  transition: background 0.15s;
}

.retry-btn:hover {
  background: rgba(59, 130, 246, 0.25);
}

.item-card {
  padding: 0.75rem;
  border-bottom: 1px solid #1e293b;
  transition: background 0.15s;
}

.item-card:hover {
  background: rgba(30, 41, 59, 0.5);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.item-name {
  color: #e2e8f0;
  font-size: 0.9rem;
  font-weight: 500;
}

.item-meta {
  color: #64748b;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.vessel-count {
  color: #94a3b8;
  margin-left: 0.5rem;
}

.risk-badge, .severity-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
}

.risk-badge.high, .severity-badge.critical { background: #991b1b; color: #fca5a5; }
.risk-badge.medium, .severity-badge.warning { background: #92400e; color: #fcd34d; }
.risk-badge.low, .severity-badge.info { background: #1e3a5f; color: #93c5fd; }

.empty-state {
  text-align: center;
  color: #475569;
  padding: 2rem 0;
  font-size: 0.9rem;
}

.flows-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.flows-table th {
  color: #64748b;
  text-align: left;
  padding: 0.5rem 0.25rem;
  font-weight: 500;
  border-bottom: 1px solid #1e293b;
}

.flows-table td {
  color: #cbd5e1;
  padding: 0.5rem 0.25rem;
  border-bottom: 1px solid #0f172a;
}

.flows-table tr:hover td {
  background: rgba(30, 41, 59, 0.4);
}

/* Voyage tab styles */
.voyage-route-row {
  color: #e2e8f0;
  font-size: 0.82rem;
  font-weight: 500;
  margin-top: 0.2rem;
}

.voyage-route-row .arrow {
  color: #64748b;
  margin: 0 0.25rem;
}

.laden-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.laden-badge.laden { background: #065f46; color: #6ee7b7; }
.laden-badge.ballast { background: #1e3a5f; color: #93c5fd; }
.laden-badge.unknown { background: #374151; color: #9ca3af; }

.cargo-tag {
  background: #374151;
  color: #d1d5db;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
  font-size: 0.7rem;
  margin-left: 0.4rem;
}

.volume-tag {
  color: #94a3b8;
  margin-left: 0.4rem;
}

.commodity-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
}

@media (max-width: 768px) {
  .right-panel {
    width: 100%;
    height: 40%;
    top: auto;
    bottom: 0;
    border-left: none;
    border-top: 1px solid #1e293b;
  }

  .toggle-btn {
    left: 50%;
    top: -28px;
    transform: translateX(-50%);
    border-radius: 6px 6px 0 0;
    border: 1px solid #334155;
    border-bottom: none;
  }
}
</style>
