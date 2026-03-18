<template>
  <div class="view-container fade-in">
    <header class="emissions-header">
      <div>
        <h1>{{ t('emissions.title') }}</h1>
        <p class="text-secondary">{{ t('emissions.subtitle') }}</p>
      </div>
      <div class="header-controls">
        <select v-model="store.timeRange" class="ss-select" @change="store.fetchEmissions()">
          <option value="1M">1M</option>
          <option value="3M">3M</option>
          <option value="6M">6M</option>
          <option value="1Y">1Y</option>
        </select>
      </div>
    </header>

    <LoadingSkeleton v-if="store.loading && !store.summary" variant="card" height="400px" />
    <ErrorState v-else-if="store.error" :retryable="true" @retry="store.fetchEmissions()" />

    <template v-else>
      <!-- KPI row -->
      <div class="kpi-grid" v-if="store.summary">
        <div class="ss-card kpi-card">
          <div class="kpi-icon kpi-icon--danger"><i class="pi pi-cloud" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ formatNumber(store.summary.total_co2) }}</span>
            <span class="kpi-label">{{ t('emissions.totalCO2') }}</span>
          </div>
        </div>
        <div class="ss-card kpi-card">
          <div class="kpi-icon kpi-icon--accent"><i class="pi pi-chart-bar" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ store.summary.avg_eeoi.toFixed(2) }}</span>
            <span class="kpi-label">{{ t('emissions.avgEEOI') }}</span>
          </div>
        </div>
        <div class="ss-card kpi-card" v-for="(count, rating) in store.summary.cii_distribution" :key="rating">
          <div class="kpi-icon" :class="ciiClass(rating as string)"><span class="cii-letter">{{ rating }}</span></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ count }}</span>
            <span class="kpi-label">CII {{ rating }}</span>
          </div>
        </div>
      </div>

      <!-- Trend chart placeholder -->
      <div class="ss-card" v-if="store.summary">
        <div class="card-header">
          <h3>{{ t('emissions.monthlyTrend') }}</h3>
        </div>
        <div class="chart-placeholder">
          <div class="trend-bars">
            <div
              v-for="(m, i) in store.summary.trend_monthly"
              :key="i"
              class="trend-bar"
              :style="{ height: barHeight(m.co2) + '%' }"
              :title="`${m.month}: ${formatNumber(m.co2)} tCO2`"
            />
          </div>
        </div>
      </div>

      <!-- Vessel table -->
      <div class="ss-card">
        <div class="card-header">
          <h3>{{ t('emissions.vesselEmissions') }}</h3>
        </div>
        <EmptyState v-if="store.vessels.length === 0" icon="pi-ship" :title="t('common.noData')" />
        <div v-else class="table-wrap">
          <table class="ss-table">
            <thead>
              <tr>
                <th>{{ t('emissions.vesselName') }}</th>
                <th>CO2 (t)</th>
                <th>{{ t('emissions.distance') }}</th>
                <th>{{ t('emissions.fuel') }}</th>
                <th>EEOI</th>
                <th>CII</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in store.vessels" :key="v.mmsi">
                <td class="vessel-name">{{ v.vessel_name }}</td>
                <td>{{ formatNumber(v.co2_tonnes) }}</td>
                <td>{{ formatNumber(v.distance_nm) }} nm</td>
                <td>{{ v.fuel_consumption_mt.toFixed(1) }} MT</td>
                <td>{{ v.eeoi.toFixed(3) }}</td>
                <td><span class="cii-badge" :class="ciiClass(v.cii_rating)">{{ v.cii_rating }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEmissionsStore } from '@/stores/useEmissionsStore'
import LoadingSkeleton from '@/components/ui/LoadingSkeleton.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const { t } = useI18n()
const store = useEmissionsStore()

onMounted(() => store.fetchEmissions())

function formatNumber(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toFixed(0)
}

function ciiClass(rating: string) {
  const map: Record<string, string> = { A: 'cii-a', B: 'cii-b', C: 'cii-c', D: 'cii-d', E: 'cii-e' }
  return map[rating] || ''
}

function barHeight(co2: number) {
  if (!store.summary) return 0
  const max = Math.max(...store.summary.trend_monthly.map(m => m.co2))
  return max > 0 ? (co2 / max) * 100 : 0
}
</script>

<style scoped>
.emissions-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.emissions-header h1 { margin: 0; font-size: 1.5rem; }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.kpi-card { display: flex; align-items: center; gap: 1rem; padding: 1.25rem; }
.kpi-icon { width: 48px; height: 48px; border-radius: var(--ss-radius); display: flex; align-items: center; justify-content: center; font-size: 1.25rem; flex-shrink: 0; }
.kpi-icon--danger { background: rgba(239,68,68,.15); color: var(--ss-danger); }
.kpi-icon--accent { background: rgba(59,130,246,.15); color: var(--ss-accent); }
.kpi-body { display: flex; flex-direction: column; }
.kpi-value { font-size: 1.5rem; font-weight: 700; color: var(--ss-text-primary); }
.kpi-label { font-size: 0.8rem; color: var(--ss-text-muted); }

.cii-letter { font-weight: 700; font-size: 1.25rem; }
.cii-a { background: rgba(34,197,94,.15); color: #22c55e; }
.cii-b { background: rgba(132,204,22,.15); color: #84cc16; }
.cii-c { background: rgba(245,158,11,.15); color: #f59e0b; }
.cii-d { background: rgba(239,68,68,.15); color: #ef4444; }
.cii-e { background: rgba(153,27,27,.15); color: #991b1b; }

.card-header { padding: 1rem 1.25rem 0.75rem; }
.card-header h3 { margin: 0; font-size: 0.95rem; font-weight: 600; }

.chart-placeholder { padding: 1rem 1.25rem 1.5rem; }
.trend-bars { display: flex; align-items: flex-end; gap: 4px; height: 200px; }
.trend-bar { flex: 1; background: var(--ss-accent); border-radius: 3px 3px 0 0; min-width: 12px; transition: height 0.3s ease; }

.table-wrap { overflow-x: auto; padding: 0 0 1rem; }
.ss-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.ss-table th { text-align: left; padding: 0.6rem 1rem; color: var(--ss-text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--ss-border-light); }
.ss-table td { padding: 0.6rem 1rem; border-bottom: 1px solid var(--ss-border-light); color: var(--ss-text-primary); }
.vessel-name { font-weight: 500; }

.cii-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: var(--ss-radius-sm); font-weight: 700; font-size: 0.8rem; }

@media (max-width: 768px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
