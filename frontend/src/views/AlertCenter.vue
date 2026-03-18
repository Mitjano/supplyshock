<template>
  <div class="view-container fade-in">
    <header class="alerts-header">
      <div class="header-left">
        <h1>{{ t('alerts.title') }}</h1>
        <span class="alert-total-badge">{{ alertStore.total }}</span>
      </div>
      <div class="header-actions">
        <button class="ss-btn ss-btn--outline ss-btn--sm" @click="alertStore.bulkMarkRead()">
          <i class="pi pi-check-circle" /> {{ t('alertCenter.markAllRead') }}
        </button>
        <button class="ss-btn ss-btn--outline ss-btn--sm" @click="alertStore.fetchAlerts()">
          <i class="pi pi-refresh" :class="{ spin: alertStore.loading }" />
        </button>
      </div>
    </header>

    <!-- Filters -->
    <div class="filters-row">
      <div class="filter-group">
        <label class="filter-label">{{ t('alerts.severity') }}</label>
        <div class="severity-toggles">
          <button
            v-for="s in severityOptions"
            :key="s"
            :class="['sev-btn', `sev-${s}`, { active: alertStore.severityFilter === s }]"
            @click="alertStore.severityFilter = alertStore.severityFilter === s ? null : s"
          >
            {{ t(`alerts.${s}`) }}
          </button>
        </div>
      </div>

      <div class="filter-group">
        <label class="filter-label">{{ t('alerts.type') }}</label>
        <select v-model="alertStore.typeFilter" class="ss-select">
          <option :value="null">{{ t('alerts.allTypes') }}</option>
          <option value="news_event">News Event</option>
          <option value="price_move">Price Move</option>
          <option value="ais_anomaly">AIS Anomaly</option>
        </select>
      </div>

      <div class="filter-group">
        <label class="filter-checkbox">
          <input type="checkbox" v-model="alertStore.unreadOnly" />
          {{ t('alertCenter.unreadOnly') }}
        </label>
      </div>
    </div>

    <!-- Alert list -->
    <LoadingSkeleton v-if="alertStore.loading && alertStore.alerts.length === 0" variant="table" :rows="8" />
    <EmptyState v-else-if="alertStore.alerts.length === 0" icon="pi-bell" :title="t('alerts.noAlertsTitle')" :description="t('alerts.noAlertsDesc')" />
    <div v-else class="alert-cards">
      <div
        v-for="alert in alertStore.alerts"
        :key="alert.id"
        class="alert-card ss-card"
        :class="{ unread: !alert.is_read }"
      >
        <div class="alert-left">
          <span class="alert-severity-dot" :class="`dot-${alert.severity}`" />
          <div class="alert-info">
            <span class="alert-title-text">{{ alert.title }}</span>
            <span class="alert-body">{{ alert.body }}</span>
            <div class="alert-tags">
              <span class="ss-badge" :class="`ss-badge--${alert.severity}`">{{ alert.severity }}</span>
              <span class="ss-badge">{{ alert.type }}</span>
              <span v-if="alert.commodity" class="ss-badge">{{ alert.commodity }}</span>
              <span v-if="alert.region" class="ss-badge">{{ alert.region }}</span>
            </div>
          </div>
        </div>
        <div class="alert-right">
          <span class="alert-time">{{ formatTime(alert.time) }}</span>
          <div class="alert-actions">
            <button
              v-if="!alert.is_read"
              class="action-btn"
              :title="t('alertCenter.markRead')"
              @click="alertStore.markAsRead(alert.id)"
            >
              <i class="pi pi-check" />
            </button>
            <button
              class="action-btn"
              :title="t('alertCenter.snooze')"
              @click="alertStore.snoozeAlert(alert.id, 4)"
            >
              <i class="pi pi-clock" />
            </button>
            <a
              v-if="alert.source_url"
              :href="alert.source_url"
              target="_blank"
              class="action-btn"
              :title="t('alerts.viewSource')"
            >
              <i class="pi pi-external-link" />
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAlertStore } from '@/stores/useAlertStore'
import LoadingSkeleton from '@/components/ui/LoadingSkeleton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const { t } = useI18n()
const alertStore = useAlertStore()
const severityOptions = ['critical', 'warning', 'info']

onMounted(() => alertStore.fetchAlerts())

watch(
  () => [alertStore.severityFilter, alertStore.typeFilter, alertStore.unreadOnly],
  () => alertStore.fetchAlerts(),
)

function formatTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('alerts.justNow')
  if (mins < 60) return t('alerts.minutesAgo', { n: mins })
  const hours = Math.floor(mins / 60)
  if (hours < 24) return t('alerts.hoursAgo', { n: hours })
  return t('alerts.daysAgo', { n: Math.floor(hours / 24) })
}
</script>

<style scoped>
.alerts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-left h1 { margin: 0; font-size: 1.5rem; }

.alert-total-badge {
  background: var(--ss-danger);
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.filters-row {
  display: flex;
  gap: 1.5rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filter-group { display: flex; flex-direction: column; gap: 0.35rem; }
.filter-label { font-size: 0.75rem; font-weight: 600; color: var(--ss-text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

.severity-toggles { display: flex; gap: 0.35rem; }

.sev-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 500;
  border-radius: var(--ss-radius);
  border: 1px solid var(--ss-border-light);
  background: none;
  color: var(--ss-text-secondary);
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.sev-btn:hover { border-color: var(--ss-accent); }
.sev-btn.active.sev-critical { background: rgba(239,68,68,.15); color: #ef4444; border-color: #ef4444; }
.sev-btn.active.sev-warning { background: rgba(245,158,11,.15); color: #f59e0b; border-color: #f59e0b; }
.sev-btn.active.sev-info { background: rgba(59,130,246,.15); color: #3b82f6; border-color: #3b82f6; }

.filter-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--ss-text-secondary);
  cursor: pointer;
}

.alert-cards { display: flex; flex-direction: column; gap: 0.5rem; }

.alert-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1rem 1.25rem;
  transition: background var(--ss-transition-fast);
}

.alert-card.unread {
  border-left: 3px solid var(--ss-accent);
}

.alert-left { display: flex; gap: 0.75rem; flex: 1; min-width: 0; }

.alert-severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 0.4rem;
  flex-shrink: 0;
}

.dot-critical { background: #ef4444; }
.dot-warning { background: #f59e0b; }
.dot-info { background: #3b82f6; }

.alert-info { display: flex; flex-direction: column; gap: 0.25rem; min-width: 0; }

.alert-title-text {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--ss-text-primary);
}

.alert-body {
  font-size: 0.8rem;
  color: var(--ss-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.alert-tags { display: flex; gap: 0.35rem; margin-top: 0.25rem; flex-wrap: wrap; }

.alert-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
  flex-shrink: 0;
  margin-left: 1rem;
}

.alert-time { font-size: 0.75rem; color: var(--ss-text-muted); white-space: nowrap; }

.alert-actions { display: flex; gap: 0.25rem; }

.action-btn {
  background: none;
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-sm);
  color: var(--ss-text-muted);
  cursor: pointer;
  padding: 0.3rem;
  font-size: 0.85rem;
  transition: all var(--ss-transition-fast);
  text-decoration: none;
  display: inline-flex;
}

.action-btn:hover {
  background: var(--ss-accent-dim);
  color: var(--ss-accent);
  border-color: var(--ss-accent);
}

.spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .alert-card { flex-direction: column; gap: 0.75rem; }
  .alert-right { flex-direction: row; justify-content: space-between; width: 100%; margin-left: 0; }
}
</style>
