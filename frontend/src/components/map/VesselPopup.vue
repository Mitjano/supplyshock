<template>
  <div class="vessel-popup" @click.self="mapStore.clearSelection()">
    <div class="popup-card">
      <button class="close-btn" @click="mapStore.clearSelection()">×</button>
      <h3>{{ vessel.vessel_name || 'Unknown Vessel' }}</h3>
      <div class="vessel-type" :style="{ color: typeColor }">{{ vessel.vessel_type }}</div>
      <table class="details">
        <tr><td>MMSI</td><td>{{ vessel.mmsi }}</td></tr>
        <tr v-if="vessel.imo"><td>IMO</td><td>{{ vessel.imo }}</td></tr>
        <tr><td>Position</td><td>{{ vessel.latitude.toFixed(4) }}°, {{ vessel.longitude.toFixed(4) }}°</td></tr>
        <tr v-if="vessel.speed_knots"><td>Speed</td><td>{{ vessel.speed_knots }} kn</td></tr>
        <tr v-if="vessel.course"><td>Course</td><td>{{ vessel.course }}°</td></tr>
        <tr v-if="vessel.destination"><td>Dest</td><td>{{ vessel.destination }}</td></tr>
        <tr v-if="vessel.flag_country"><td>Flag</td><td>{{ vessel.flag_country }}</td></tr>
        <tr v-if="vessel.draught"><td>Draught</td><td>{{ vessel.draught }}m</td></tr>
      </table>
      <div class="time">Last update: {{ new Date(vessel.time).toLocaleTimeString() }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/useMapStore'

const mapStore = useMapStore()
const vessel = computed(() => mapStore.selectedVessel!)

const COLORS: Record<string, string> = {
  tanker: '#ef4444',
  bulk_carrier: '#f59e0b',
  container: '#3b82f6',
  lng_carrier: '#10b981',
  other: '#6b7280',
}

const typeColor = computed(() => COLORS[vessel.value.vessel_type] || COLORS.other)
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
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1.5rem;
  min-width: 280px;
  position: relative;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

.close-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.75rem;
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 1.5rem;
  cursor: pointer;
}

h3 {
  color: #f1f5f9;
  margin: 0 0 0.25rem 0;
}

.vessel-type {
  font-size: 0.85rem;
  text-transform: uppercase;
  font-weight: 600;
  margin-bottom: 1rem;
}

.details {
  width: 100%;
  border-collapse: collapse;
}

.details td {
  padding: 0.25rem 0;
  color: #cbd5e1;
  font-size: 0.9rem;
}

.details td:first-child {
  color: #64748b;
  width: 80px;
}

.time {
  margin-top: 0.75rem;
  font-size: 0.8rem;
  color: #475569;
}
</style>
