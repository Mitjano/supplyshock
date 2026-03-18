<template>
  <div class="trends-sparklines">
    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" /> {{ t('common.loading') }}
    </div>
    <div v-else-if="items.length === 0" class="empty-state-inline">
      {{ t('common.noData') }}
    </div>
    <div v-else class="sparkline-grid">
      <div v-for="item in items" :key="item.commodity" class="sparkline-card ss-card">
        <div class="spark-header">
          <span class="spark-name">{{ formatName(item.commodity) }}</span>
          <span class="spark-trend" :class="item.trend">
            <i :class="['pi', trendIcon(item.trend)]" />
            {{ t(`analytics.trend.${item.trend}`) }}
          </span>
        </div>
        <svg class="spark-svg" viewBox="0 0 100 30" preserveAspectRatio="none">
          <polyline
            :points="sparkPoints(item.values)"
            fill="none"
            :stroke="trendColor(item.trend)"
            stroke-width="2"
          />
        </svg>
        <div class="spark-footer">
          <span class="spark-volume">{{ formatVolume(item.values[item.values.length - 1]) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useApi } from '@/composables/useApi'

const { t } = useI18n()
const api = useApi()

interface TrendItem {
  commodity: string
  trend: 'growing' | 'declining' | 'stable'
  values: number[]
}

const items = ref<TrendItem[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await api.get<{ data: TrendItem[] }>('/analytics/supply-trends')
    items.value = res.data
  } catch { /* ignore */ } finally {
    loading.value = false
  }
})

function formatName(name: string) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatVolume(v: number) {
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M'
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K'
  return v?.toFixed(0) ?? '--'
}

function trendIcon(trend: string) {
  return trend === 'growing' ? 'pi-arrow-up' : trend === 'declining' ? 'pi-arrow-down' : 'pi-minus'
}

function trendColor(trend: string) {
  return trend === 'growing' ? '#22c55e' : trend === 'declining' ? '#ef4444' : '#f59e0b'
}

function sparkPoints(values: number[]) {
  if (!values || values.length < 2) return '0,15 100,15'
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100
    const y = 28 - ((v - min) / range) * 24
    return `${x},${y}`
  }).join(' ')
}
</script>

<style scoped>
.sparkline-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}

.sparkline-card { padding: 0.75rem 1rem; }

.spark-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.spark-name { font-weight: 600; font-size: 0.85rem; color: var(--ss-text-primary); text-transform: capitalize; }
.spark-trend { font-size: 0.75rem; font-weight: 500; display: flex; align-items: center; gap: 0.25rem; }
.spark-trend.growing { color: #22c55e; }
.spark-trend.declining { color: #ef4444; }
.spark-trend.stable { color: #f59e0b; }

.spark-svg { width: 100%; height: 30px; }

.spark-footer { margin-top: 0.35rem; }
.spark-volume { font-size: 0.75rem; color: var(--ss-text-muted); }

.loading-state, .empty-state-inline { padding: 2rem; text-align: center; color: var(--ss-text-muted); }
</style>
