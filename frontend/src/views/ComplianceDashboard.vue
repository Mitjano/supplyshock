<template>
  <div class="compliance-dashboard">
    <header class="page-header">
      <div class="header-left">
        <h1>{{ t('compliance.title') }}</h1>
        <span class="header-subtitle">{{ t('compliance.subtitle') }}</span>
      </div>
      <div class="header-filters">
        <select v-model="severityFilter" class="filter-select">
          <option value="">{{ t('compliance.allSeverities') }}</option>
          <option value="critical">{{ t('compliance.severity.critical') }}</option>
          <option value="high">{{ t('compliance.severity.high') }}</option>
          <option value="medium">{{ t('compliance.severity.medium') }}</option>
          <option value="low">{{ t('compliance.severity.low') }}</option>
        </select>
        <select v-model="hoursRange" class="filter-select">
          <option :value="24">24h</option>
          <option :value="48">48h</option>
          <option :value="72">72h</option>
          <option :value="168">7d</option>
        </select>
      </div>
    </header>

    <!-- Tabs -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        <i :class="['pi', tab.icon]" />
        {{ tab.label }}
        <span v-if="tab.count > 0" class="tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- Sanctions Tab -->
    <div v-if="activeTab === 'sanctions'" class="tab-content">
      <!-- Loading skeleton -->
      <div v-if="store.loadingFlagged" class="table-skeleton">
        <div v-for="i in 5" :key="i" class="skeleton-row">
          <div class="skeleton-line skeleton-cell-wide" />
          <div class="skeleton-line skeleton-cell" />
          <div class="skeleton-line skeleton-cell" />
          <div class="skeleton-line skeleton-cell-narrow" />
        </div>
      </div>

      <!-- Error state -->
      <div v-else-if="store.errorFlagged" class="error-state">
        <i class="pi pi-exclamation-triangle error-icon" />
        <p>{{ t('common.error') }}</p>
        <button class="retry-btn" @click="loadSanctions">
          <i class="pi pi-refresh" /> {{ t('common.retry') }}
        </button>
      </div>

      <!-- Empty state -->
      <div v-else-if="filteredFlagged.length === 0" class="empty-state">
        <i class="pi pi-check-circle" />
        <p>{{ t('compliance.noFlagged') }}</p>
      </div>

      <!-- Table -->
      <div v-else class="data-table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('compliance.vesselName') }}</th>
              <th>MMSI</th>
              <th>IMO</th>
              <th>{{ t('compliance.sanctionSource') }}</th>
              <th>{{ t('compliance.program') }}</th>
              <th>{{ t('compliance.matchType') }}</th>
              <th>{{ t('compliance.severity.label') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in filteredFlagged" :key="v.mmsi">
              <td class="cell-name">{{ v.vessel_name }}</td>
              <td class="cell-mono">{{ v.mmsi }}</td>
              <td class="cell-mono">{{ v.imo ?? '—' }}</td>
              <td>{{ v.sanction_source }}</td>
              <td>{{ v.program }}</td>
              <td><span class="match-badge">{{ v.match_type }}</span></td>
              <td>
                <span :class="['severity-badge', `severity-${v.severity}`]">
                  {{ t(`compliance.severity.${v.severity}`) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- AIS Gaps Tab -->
    <div v-if="activeTab === 'aisGaps'" class="tab-content">
      <div v-if="store.loadingAisGaps" class="table-skeleton">
        <div v-for="i in 5" :key="i" class="skeleton-row">
          <div class="skeleton-line skeleton-cell-wide" />
          <div class="skeleton-line skeleton-cell" />
          <div class="skeleton-line skeleton-cell" />
          <div class="skeleton-line skeleton-cell-narrow" />
        </div>
      </div>

      <div v-else-if="store.errorAisGaps" class="error-state">
        <i class="pi pi-exclamation-triangle error-icon" />
        <p>{{ t('common.error') }}</p>
        <button class="retry-btn" @click="loadAisGaps">
          <i class="pi pi-refresh" /> {{ t('common.retry') }}
        </button>
      </div>

      <div v-else-if="store.aisGaps.length === 0" class="empty-state">
        <i class="pi pi-check-circle" />
        <p>{{ t('compliance.noAisGaps') }}</p>
      </div>

      <div v-else class="data-table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('compliance.vesselName') }}</th>
              <th>{{ t('compliance.lastSeen') }}</th>
              <th>{{ t('compliance.lastSeenTime') }}</th>
              <th>{{ t('compliance.reappeared') }}</th>
              <th>{{ t('compliance.reappearedTime') }}</th>
              <th>{{ t('compliance.gapHours') }}</th>
              <th>{{ t('compliance.distanceNm') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(gap, idx) in store.aisGaps" :key="idx">
              <td class="cell-name">{{ gap.vessel_name }}</td>
              <td class="cell-mono">{{ gap.last_seen_lat.toFixed(2) }}, {{ gap.last_seen_lon.toFixed(2) }}</td>
              <td>{{ formatTime(gap.last_seen_time) }}</td>
              <td class="cell-mono">{{ gap.reappeared_lat.toFixed(2) }}, {{ gap.reappeared_lon.toFixed(2) }}</td>
              <td>{{ formatTime(gap.reappeared_time) }}</td>
              <td :class="['cell-mono', { 'text-warning': gap.gap_hours > 12 }]">{{ gap.gap_hours.toFixed(1) }}h</td>
              <td :class="['cell-mono', { 'text-danger': gap.distance_nm > 200 }]">{{ gap.distance_nm.toFixed(0) }} nm</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- STS Events Tab -->
    <div v-if="activeTab === 'stsEvents'" class="tab-content">
      <div v-if="store.loadingSts" class="table-skeleton">
        <div v-for="i in 5" :key="i" class="skeleton-row">
          <div class="skeleton-line skeleton-cell-wide" />
          <div class="skeleton-line skeleton-cell" />
          <div class="skeleton-line skeleton-cell" />
          <div class="skeleton-line skeleton-cell-narrow" />
        </div>
      </div>

      <div v-else-if="store.errorSts" class="error-state">
        <i class="pi pi-exclamation-triangle error-icon" />
        <p>{{ t('common.error') }}</p>
        <button class="retry-btn" @click="loadStsEvents">
          <i class="pi pi-refresh" /> {{ t('common.retry') }}
        </button>
      </div>

      <div v-else-if="store.stsEvents.length === 0" class="empty-state">
        <i class="pi pi-check-circle" />
        <p>{{ t('compliance.noStsEvents') }}</p>
      </div>

      <div v-else class="data-table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ t('compliance.vesselA') }}</th>
              <th>{{ t('compliance.vesselB') }}</th>
              <th>{{ t('compliance.location') }}</th>
              <th>{{ t('compliance.detectedAt') }}</th>
              <th>{{ t('compliance.ladenStatusA') }}</th>
              <th>{{ t('compliance.ladenStatusB') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(evt, idx) in store.stsEvents" :key="idx">
              <td class="cell-name">{{ evt.vessel_a_name }} <span class="mmsi-sub">{{ evt.vessel_a_mmsi }}</span></td>
              <td class="cell-name">{{ evt.vessel_b_name }} <span class="mmsi-sub">{{ evt.vessel_b_mmsi }}</span></td>
              <td class="cell-mono">{{ evt.latitude.toFixed(2) }}, {{ evt.longitude.toFixed(2) }}</td>
              <td>{{ formatTime(evt.detected_at) }}</td>
              <td><span :class="ladenClass(evt.vessel_a_laden)">{{ ladenLabel(evt.vessel_a_laden) }}</span></td>
              <td><span :class="ladenClass(evt.vessel_b_laden)">{{ ladenLabel(evt.vessel_b_laden) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useComplianceStore } from '@/stores/useComplianceStore'

const { t } = useI18n()
const store = useComplianceStore()

const activeTab = ref<'sanctions' | 'aisGaps' | 'stsEvents'>('sanctions')
const severityFilter = ref('')
const hoursRange = ref(24)

const tabs = computed(() => [
  { key: 'sanctions' as const, icon: 'pi-shield', label: t('compliance.tabs.sanctions'), count: store.flaggedVessels.length },
  { key: 'aisGaps' as const, icon: 'pi-eye-slash', label: t('compliance.tabs.aisGaps'), count: store.aisGaps.length },
  { key: 'stsEvents' as const, icon: 'pi-arrows-h', label: t('compliance.tabs.stsEvents'), count: store.stsEvents.length },
])

const filteredFlagged = computed(() => {
  if (!severityFilter.value) return store.flaggedVessels
  return store.flaggedVessels.filter(v => v.severity === severityFilter.value)
})

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function ladenLabel(laden: boolean | null): string {
  if (laden === true) return t('map.laden')
  if (laden === false) return t('map.ballast')
  return t('map.unknown')
}

function ladenClass(laden: boolean | null): string {
  if (laden === true) return 'laden-badge laden'
  if (laden === false) return 'laden-badge ballast'
  return 'laden-badge unknown'
}

async function loadSanctions() {
  await store.fetchFlagged(severityFilter.value || undefined)
}

async function loadAisGaps() {
  await store.fetchAisGaps(hoursRange.value)
}

async function loadStsEvents() {
  await store.fetchStsEvents(hoursRange.value)
}

// Re-fetch when filters change
watch(severityFilter, () => {
  if (activeTab.value === 'sanctions') loadSanctions()
})
watch(hoursRange, () => {
  if (activeTab.value === 'aisGaps') loadAisGaps()
  if (activeTab.value === 'stsEvents') loadStsEvents()
})

// Fetch active tab data on tab switch
watch(activeTab, (tab) => {
  if (tab === 'sanctions' && store.flaggedVessels.length === 0) loadSanctions()
  if (tab === 'aisGaps' && store.aisGaps.length === 0) loadAisGaps()
  if (tab === 'stsEvents' && store.stsEvents.length === 0) loadStsEvents()
})

onMounted(() => {
  loadSanctions()
})
</script>

<style scoped>
.compliance-dashboard {
  padding: 1.5rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
  color: var(--ss-text-primary);
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.page-header h1 {
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
}

.header-subtitle {
  color: var(--ss-text-muted);
  font-size: 0.85rem;
}

.header-filters {
  display: flex;
  gap: 0.5rem;
}

.filter-select {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  color: var(--ss-text-primary);
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
  outline: none;
  transition: border-color var(--ss-transition-fast);
}

.filter-select:focus {
  border-color: var(--ss-accent);
}

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--ss-border);
  margin-bottom: 1.25rem;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--ss-text-muted);
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.tab-btn:hover {
  color: var(--ss-text-primary);
}

.tab-btn.active {
  color: var(--ss-accent);
  border-bottom-color: var(--ss-accent);
}

.tab-btn i {
  font-size: 0.8rem;
}

.tab-count {
  background: var(--ss-bg-elevated);
  color: var(--ss-text-secondary);
  padding: 1px 6px;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 600;
}

.tab-btn.active .tab-count {
  background: rgba(20, 184, 166, 0.15);
  color: var(--ss-accent);
}

/* Table */
.data-table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.data-table thead th {
  text-align: left;
  padding: 0.6rem 0.75rem;
  color: var(--ss-text-muted);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 1px solid var(--ss-border);
  white-space: nowrap;
}

.data-table tbody tr {
  border-bottom: 1px solid var(--ss-border-light);
  transition: background var(--ss-transition-fast);
}

.data-table tbody tr:hover {
  background: rgba(20, 184, 166, 0.03);
}

.data-table td {
  padding: 0.65rem 0.75rem;
  vertical-align: middle;
}

.cell-name {
  font-weight: 600;
  color: var(--ss-text-primary);
}

.cell-mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: var(--ss-text-secondary);
}

.mmsi-sub {
  display: block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--ss-text-muted);
}

/* Badges */
.severity-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 9999px;
  letter-spacing: 0.03em;
}

.severity-critical { background: rgba(239, 68, 68, 0.15); color: var(--ss-danger); }
.severity-high { background: rgba(249, 115, 22, 0.15); color: #f97316; }
.severity-medium { background: rgba(234, 179, 8, 0.15); color: #eab308; }
.severity-low { background: rgba(34, 197, 94, 0.15); color: var(--ss-success); }

.match-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--ss-bg-elevated);
  color: var(--ss-text-secondary);
  text-transform: capitalize;
}

.laden-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 9999px;
}

.laden-badge.laden { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }
.laden-badge.ballast { background: rgba(59, 130, 246, 0.12); color: #93c5fd; }
.laden-badge.unknown { background: var(--ss-bg-elevated); color: var(--ss-text-muted); }

.text-warning { color: #eab308; }
.text-danger { color: var(--ss-danger); }

/* Empty / Error states */
.empty-state, .error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 1rem;
  color: var(--ss-text-muted);
  gap: 0.75rem;
}

.empty-state i, .error-state .error-icon {
  font-size: 2.5rem;
  opacity: 0.5;
}

.error-state .error-icon {
  color: var(--ss-warning);
  opacity: 1;
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  color: var(--ss-text-primary);
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.retry-btn:hover {
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

/* Skeleton */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-line {
  background: linear-gradient(
    90deg,
    var(--ss-bg-elevated) 25%,
    rgba(100, 116, 139, 0.15) 50%,
    var(--ss-bg-elevated) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite ease-in-out;
  border-radius: 4px;
}

.table-skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 0;
}

.skeleton-row {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.skeleton-cell-wide { height: 14px; width: 200px; }
.skeleton-cell { height: 14px; width: 120px; }
.skeleton-cell-narrow { height: 14px; width: 60px; }

/* Responsive */
@media (max-width: 768px) {
  .compliance-dashboard {
    padding: 1rem;
  }

  .page-header {
    flex-direction: column;
    gap: 0.75rem;
  }

  .tab-btn {
    padding: 0.5rem 0.6rem;
    font-size: 0.8rem;
  }

  .data-table {
    font-size: 0.8rem;
  }
}
</style>
