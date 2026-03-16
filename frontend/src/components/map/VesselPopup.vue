<template>
  <div class="vessel-popup" @click.self="mapStore.clearSelection()">
    <div class="popup-card">
      <button class="close-btn" @click="mapStore.clearSelection()">&times;</button>

      <!-- Header -->
      <div class="popup-header">
        <span v-if="flagEmoji" class="flag-emoji">{{ flagEmoji }}</span>
        <div>
          <h3>{{ vessel.vessel_name || t('map.unknownVessel') }}</h3>
          <div class="vessel-type" :style="{ color: typeColor }">
            {{ formatType(vessel.vessel_type) }}
          </div>
        </div>
      </div>

      <!-- Details table -->
      <table class="details">
        <tr><td>MMSI</td><td>{{ vessel.mmsi }}</td></tr>
        <tr v-if="vessel.imo"><td>IMO</td><td>{{ vessel.imo }}</td></tr>
        <tr>
          <td>{{ t('map.position') }}</td>
          <td>{{ vessel.latitude.toFixed(4) }}, {{ vessel.longitude.toFixed(4) }}</td>
        </tr>
        <tr v-if="vessel.speed_knots != null">
          <td>{{ t('map.speed') }}</td>
          <td>{{ vessel.speed_knots }} kn</td>
        </tr>
        <tr v-if="vessel.course != null">
          <td>{{ t('map.course') }}</td>
          <td>{{ vessel.course }}</td>
        </tr>
        <tr v-if="vessel.destination">
          <td>{{ t('map.destination') }}</td>
          <td>{{ vessel.destination }}</td>
        </tr>
        <tr v-if="vessel.flag_country">
          <td>{{ t('map.flag') }}</td>
          <td>{{ flagEmoji }} {{ vessel.flag_country }}</td>
        </tr>
        <tr v-if="vessel.draught">
          <td>{{ t('map.draught') }}</td>
          <td>{{ vessel.draught }}m</td>
        </tr>
      </table>

      <div class="time">{{ t('map.lastUpdate') }}: {{ new Date(vessel.time).toLocaleTimeString() }}</div>

      <!-- Trail button -->
      <div class="popup-actions">
        <button
          v-if="!props.trailVisible"
          class="trail-btn"
          :disabled="mapStore.trailLoading"
          @click="$emit('viewTrail', vessel.mmsi)"
        >
          <i class="pi pi-directions"></i>
          {{ mapStore.trailLoading ? t('map.loadingTrail') : t('map.viewTrail') }}
        </button>
        <button
          v-else
          class="trail-btn trail-btn--active"
          @click="$emit('hideTrail')"
        >
          <i class="pi pi-times"></i>
          {{ t('map.hideTrail') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMapStore } from '../../stores/useMapStore'

const { t } = useI18n()
const mapStore = useMapStore()

const props = defineProps<{
  trailVisible: boolean
}>()

defineEmits<{
  viewTrail: [mmsi: number]
  hideTrail: []
}>()

const vessel = computed(() => mapStore.selectedVessel!)

const COLORS: Record<string, string> = {
  tanker: '#ef4444',
  bulk_carrier: '#f59e0b',
  container: '#3b82f6',
  lng_carrier: '#10b981',
  other: '#6b7280',
}

const typeColor = computed(() => COLORS[vessel.value.vessel_type] || COLORS.other)

function formatType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Convert 2-letter country code to flag emoji
const flagEmoji = computed(() => {
  const code = vessel.value.flag_country
  if (!code || code.length !== 2) return ''
  const codePoints = [...code.toUpperCase()].map(
    c => 0x1f1e6 + c.charCodeAt(0) - 65
  )
  return String.fromCodePoint(...codePoints)
})
</script>

<style scoped>
.vessel-popup {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  pointer-events: auto;
}

.popup-card {
  background: rgba(15, 23, 42, 0.97);
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.5rem;
  min-width: 300px;
  max-width: 360px;
  position: relative;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(59, 130, 246, 0.1);
  backdrop-filter: blur(12px);
}

.close-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.75rem;
  background: none;
  border: none;
  color: #64748b;
  font-size: 1.5rem;
  cursor: pointer;
  transition: color 0.15s;
}

.close-btn:hover {
  color: #f1f5f9;
}

/* Header with flag */
.popup-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.flag-emoji {
  font-size: 1.8rem;
  line-height: 1;
  margin-top: 0.1rem;
}

h3 {
  color: #f1f5f9;
  margin: 0 0 0.15rem 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.vessel-type {
  font-size: 0.8rem;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.details {
  width: 100%;
  border-collapse: collapse;
}

.details td {
  padding: 0.3rem 0;
  color: #cbd5e1;
  font-size: 0.875rem;
}

.details td:first-child {
  color: #64748b;
  width: 80px;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.time {
  margin-top: 0.75rem;
  font-size: 0.75rem;
  color: #475569;
}

/* Actions */
.popup-actions {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
}

.trail-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  color: #60a5fa;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.trail-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.25);
  border-color: rgba(59, 130, 246, 0.5);
}

.trail-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.trail-btn--active {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.trail-btn--active:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.5);
}
</style>
