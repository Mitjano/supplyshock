<template>
  <div class="congestion-panel">
    <div class="panel-header">
      <h2>{{ t('analytics.congestion.title') }}</h2>
      <span class="text-muted auto-refresh-badge">
        <i class="pi pi-sync" :class="{ spinning: loading }" />
        {{ t('analytics.congestion.autoRefresh') }}
      </span>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && ports.length === 0" class="port-grid">
      <div v-for="i in 4" :key="i" class="ss-card port-card skeleton-card">
        <div class="skeleton-line skeleton-title" />
        <div class="skeleton-line skeleton-bar" />
        <div class="skeleton-line skeleton-value" />
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="fetchTopPorts">{{ t('common.retry') }}</button>
    </div>

    <!-- Port cards -->
    <div v-else class="port-grid">
      <div
        v-for="port in ports"
        :key="port.port_id"
        class="ss-card port-card"
        :class="{ expanded: expandedPort === port.port_id }"
        @click="togglePort(port.port_id)"
      >
        <div class="port-card-header">
          <span class="port-name">{{ port.name }}</span>
          <span class="risk-badge" :class="'risk-' + port.risk_level">
            {{ t('analytics.congestion.risk.' + port.risk_level) }}
          </span>
        </div>

        <div class="congestion-bar-wrapper">
          <div class="congestion-bar">
            <div
              class="congestion-fill"
              :class="'fill-' + port.risk_level"
              :style="{ width: port.congestion_index + '%' }"
            />
          </div>
          <span class="congestion-value">{{ port.congestion_index }}%</span>
        </div>

        <div class="port-meta">
          <span class="waiting-vessels">
            <i class="pi pi-map-marker" />
            {{ t('analytics.congestion.waitingVessels', { count: port.waiting_vessels }) }}
          </span>
        </div>

        <!-- Expanded detail: vessel list -->
        <Transition name="expand">
          <div v-if="expandedPort === port.port_id" class="port-detail">
            <div v-if="detailLoading" class="detail-loading">
              <i class="pi pi-spin pi-spinner" />
            </div>
            <div v-else-if="portVessels.length === 0" class="text-muted detail-empty">
              {{ t('common.noData') }}
            </div>
            <ul v-else class="vessel-list">
              <li v-for="vessel in portVessels" :key="vessel.mmsi" class="vessel-item">
                <span class="vessel-name">{{ vessel.vessel_name || t('map.unknownVessel') }}</span>
                <span class="vessel-type text-muted">{{ vessel.vessel_type }}</span>
                <span class="vessel-wait text-muted">{{ vessel.waiting_hours }}h</span>
              </li>
            </ul>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMapStore } from '../stores/useMapStore'

const { t } = useI18n()
const mapStore = useMapStore()

interface PortCongestion {
  port_id: string
  name: string
  congestion_index: number
  risk_level: 'normal' | 'elevated' | 'high' | 'critical'
  waiting_vessels: number
}

interface PortVessel {
  mmsi: number
  vessel_name: string | null
  vessel_type: string
  waiting_hours: number
}

const ports = ref<PortCongestion[]>([])
const loading = ref(false)
const error = ref(false)
const expandedPort = ref<string | null>(null)
const detailLoading = ref(false)
const portVessels = ref<PortVessel[]>([])
let refreshInterval: ReturnType<typeof setInterval> | null = null

async function fetchTopPorts() {
  loading.value = true
  error.value = false
  try {
    const data = await mapStore.fetchPortCongestion('top10')
    ports.value = data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function togglePort(portId: string) {
  if (expandedPort.value === portId) {
    expandedPort.value = null
    portVessels.value = []
    return
  }
  expandedPort.value = portId
  detailLoading.value = true
  try {
    const data = await mapStore.fetchPortCongestion(portId)
    portVessels.value = data.vessels || []
  } catch {
    portVessels.value = []
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  fetchTopPorts()
  refreshInterval = setInterval(fetchTopPorts, 5 * 60_000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<style scoped>
.congestion-panel { margin-bottom: 1.5rem; }

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.panel-header h2 { font-size: 1.1rem; font-weight: 600; }

.auto-refresh-badge {
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.port-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.port-card {
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid var(--border-color, #2a2a3e);
}
.port-card:hover { border-color: var(--accent, #3b82f6); }
.port-card.expanded { border-color: var(--accent, #3b82f6); background: var(--bg-hover, rgba(59,130,246,0.08)); }

.port-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}
.port-name { font-weight: 600; font-size: 0.95rem; }

.risk-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.risk-normal { background: rgba(34,197,94,0.15); color: #4ade80; }
.risk-elevated { background: rgba(234,179,8,0.15); color: #facc15; }
.risk-high { background: rgba(249,115,22,0.15); color: #fb923c; }
.risk-critical { background: rgba(239,68,68,0.15); color: #f87171; }

.congestion-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.congestion-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-hover, #1e293b);
  border-radius: 3px;
  overflow: hidden;
}
.congestion-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}
.fill-normal { background: #4ade80; }
.fill-elevated { background: #facc15; }
.fill-high { background: #fb923c; }
.fill-critical { background: #f87171; }
.congestion-value { font-size: 0.8rem; font-weight: 600; min-width: 2.5rem; text-align: right; }

.port-meta { font-size: 0.8rem; }
.waiting-vessels {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--text-secondary, #94a3b8);
}

.port-detail { margin-top: 0.75rem; border-top: 1px solid var(--border-color, #2a2a3e); padding-top: 0.75rem; }
.detail-loading { text-align: center; padding: 0.5rem; color: var(--text-secondary, #94a3b8); }
.detail-empty { text-align: center; padding: 0.5rem; font-size: 0.85rem; }

.vessel-list { list-style: none; padding: 0; margin: 0; }
.vessel-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0;
  font-size: 0.85rem;
  gap: 0.5rem;
}
.vessel-item .vessel-name { font-weight: 500; flex: 1; }
.vessel-item .vessel-type { font-size: 0.75rem; }
.vessel-item .vessel-wait { font-size: 0.75rem; white-space: nowrap; }

.expand-enter-active,
.expand-leave-active { transition: all 0.25s ease; overflow: hidden; }
.expand-enter-from,
.expand-leave-to { opacity: 0; max-height: 0; }
.expand-enter-to,
.expand-leave-from { opacity: 1; max-height: 300px; }

.error-state { text-align: center; padding: 2rem; color: var(--text-secondary); }
.error-state i { font-size: 1.5rem; margin-bottom: 0.5rem; display: block; }

.skeleton-card { animation: pulse 1.5s ease-in-out infinite; }
.skeleton-title { height: 1rem; width: 60%; background: var(--bg-hover, #2a2a3e); border-radius: 4px; margin-bottom: 0.5rem; }
.skeleton-value { height: 0.8rem; width: 30%; background: var(--bg-hover, #2a2a3e); border-radius: 4px; margin-top: 0.5rem; }
.skeleton-bar { height: 6px; background: var(--bg-hover, #2a2a3e); border-radius: 3px; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
