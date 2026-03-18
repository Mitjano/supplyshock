<template>
  <div class="view-container fade-in">
    <header class="view-header">
      <h1>{{ t('analytics.fleet.title') }}</h1>
    </header>

    <div v-if="store.loading" class="ss-card" style="padding: 2rem; text-align: center">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
      <p class="text-muted">{{ t('common.loading') }}</p>
    </div>

    <div v-else-if="store.error" class="error-state">
      <i class="pi pi-exclamation-triangle" />
      <p>{{ t('common.error') }}</p>
      <button class="ss-btn" @click="store.fetchFleet()">{{ t('common.retry') }}</button>
    </div>

    <div v-else class="ss-card fleet-table-card">
      <table class="ss-table">
        <thead>
          <tr>
            <th class="sortable" @click="toggleSort('owner_name')">
              {{ t('analytics.fleet.owner') }}
              <i v-if="sortKey === 'owner_name'" :class="sortIcon" />
            </th>
            <th class="sortable" @click="toggleSort('vessel_count')">
              {{ t('analytics.fleet.vesselCount') }}
              <i v-if="sortKey === 'vessel_count'" :class="sortIcon" />
            </th>
            <th class="sortable" @click="toggleSort('total_dwt')">
              {{ t('analytics.fleet.totalDwt') }}
              <i v-if="sortKey === 'total_dwt'" :class="sortIcon" />
            </th>
            <th class="sortable" @click="toggleSort('utilization')">
              {{ t('analytics.fleet.utilization') }}
              <i v-if="sortKey === 'utilization'" :class="sortIcon" />
            </th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="owner in sortedOwners" :key="owner.owner_id">
            <tr class="owner-row" @click="toggleExpand(owner.owner_id)">
              <td><strong>{{ owner.owner_name }}</strong></td>
              <td>{{ owner.vessel_count }}</td>
              <td>{{ (owner.total_dwt / 1000).toFixed(0) }}k DWT</td>
              <td>
                <div class="util-bar">
                  <div class="util-fill" :style="{ width: owner.utilization + '%' }" :class="utilClass(owner.utilization)" />
                </div>
                <span class="util-pct">{{ owner.utilization.toFixed(0) }}%</span>
              </td>
              <td><i :class="['pi', expanded === owner.owner_id ? 'pi-chevron-up' : 'pi-chevron-down']" /></td>
            </tr>
            <!-- Expanded vessel detail -->
            <tr v-if="expanded === owner.owner_id" class="detail-row">
              <td colspan="5">
                <div v-if="detailLoading" class="text-muted" style="padding: 1rem; text-align: center">{{ t('common.loading') }}</div>
                <table v-else-if="expandedVessels.length > 0" class="ss-table ss-table--nested">
                  <thead>
                    <tr>
                      <th>{{ t('analytics.fleet.vesselName') }}</th>
                      <th>{{ t('analytics.fleet.type') }}</th>
                      <th>DWT</th>
                      <th>{{ t('analytics.fleet.flag') }}</th>
                      <th>{{ t('analytics.fleet.status') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="v in expandedVessels" :key="v.imo">
                      <td>{{ v.vessel_name }}</td>
                      <td>{{ v.vessel_type }}</td>
                      <td>{{ v.dwt ? v.dwt.toLocaleString() : '—' }}</td>
                      <td>{{ v.flag || '—' }}</td>
                      <td>
                        <span class="status-badge" :class="'status-' + v.status">{{ v.status }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div v-else class="text-muted" style="padding: 1rem; text-align: center">{{ t('common.noData') }}</div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFleetStore, type FleetVessel } from '@/stores/useFleetStore'

const { t } = useI18n()
const store = useFleetStore()

const sortKey = ref<'owner_name' | 'vessel_count' | 'total_dwt' | 'utilization'>('vessel_count')
const sortAsc = ref(false)
const expanded = ref<string | null>(null)
const expandedVessels = ref<FleetVessel[]>([])
const detailLoading = ref(false)

const sortIcon = computed(() => sortAsc.value ? 'pi pi-sort-amount-up-alt' : 'pi pi-sort-amount-down')

const sortedOwners = computed(() => {
  const list = [...store.owners]
  const key = sortKey.value
  list.sort((a, b) => {
    const av = a[key] as any
    const bv = b[key] as any
    if (typeof av === 'string') return sortAsc.value ? av.localeCompare(bv) : bv.localeCompare(av)
    return sortAsc.value ? av - bv : bv - av
  })
  return list
})

function toggleSort(key: typeof sortKey.value) {
  if (sortKey.value === key) { sortAsc.value = !sortAsc.value }
  else { sortKey.value = key; sortAsc.value = false }
}

async function toggleExpand(ownerId: string) {
  if (expanded.value === ownerId) { expanded.value = null; return }
  expanded.value = ownerId
  detailLoading.value = true
  const detail = await store.fetchOwnerDetail(ownerId)
  expandedVessels.value = detail?.vessels || []
  detailLoading.value = false
}

function utilClass(pct: number): string {
  if (pct >= 80) return 'high'
  if (pct >= 50) return 'mid'
  return 'low'
}

onMounted(() => store.fetchFleet())
</script>

<style scoped>
.view-header { margin-bottom: 1.5rem; }
.view-header h1 { font-size: 1.5rem; font-weight: 700; }
.fleet-table-card { padding: 1rem; overflow-x: auto; }
.sortable { cursor: pointer; user-select: none; white-space: nowrap; }
.sortable:hover { color: var(--ss-accent); }
.sortable i { font-size: 0.7rem; margin-left: 0.25rem; }
.owner-row { cursor: pointer; transition: background 0.15s; }
.owner-row:hover { background: var(--ss-accent-dim); }
.detail-row td { padding: 0 !important; background: var(--ss-bg-base); }
.ss-table--nested { margin: 0; font-size: 0.85rem; }
.ss-table--nested th { font-size: 0.75rem; color: var(--ss-text-muted); }
.util-bar { width: 60px; height: 6px; background: var(--ss-bg-base); border-radius: 3px; display: inline-block; vertical-align: middle; margin-right: 0.5rem; }
.util-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.util-fill.high { background: #4ade80; }
.util-fill.mid { background: #fbbf24; }
.util-fill.low { background: #f87171; }
.util-pct { font-size: 0.8rem; font-weight: 600; }
.status-badge { padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; text-transform: capitalize; }
.status-laden { background: rgba(59,130,246,0.15); color: #60a5fa; }
.status-ballast { background: rgba(148,163,184,0.15); color: #94a3b8; }
.status-idle { background: rgba(251,191,36,0.15); color: #fbbf24; }
.status-in_port { background: rgba(34,197,94,0.15); color: #4ade80; }
.error-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.error-state i { font-size: 2rem; margin-bottom: 1rem; display: block; }
</style>
