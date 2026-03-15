<template>
  <div class="map-legend">
    <h4>Vessels</h4>
    <div v-for="(color, type) in vesselColors" :key="type" class="legend-item">
      <span class="dot" :style="{ background: color }"></span>
      <span>{{ formatType(type) }}</span>
    </div>
    <h4>Commodities</h4>
    <div v-for="(color, commodity) in commodityColors" :key="commodity" class="legend-item">
      <span class="line" :style="{ background: color }"></span>
      <span>{{ formatType(commodity) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const vesselColors: Record<string, string> = {
  tanker: '#ef4444',
  bulk_carrier: '#f59e0b',
  container: '#3b82f6',
  lng_carrier: '#10b981',
  other: '#6b7280',
}

const commodityColors: Record<string, string> = {
  crude_oil: '#ef4444',
  coal: '#374151',
  iron_ore: '#b45309',
  copper: '#d97706',
  lng: '#10b981',
}

function formatType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}
</script>

<style scoped>
.map-legend {
  position: absolute;
  bottom: 2rem;
  left: 1rem;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  z-index: 10;
  min-width: 140px;
}

h4 {
  color: #94a3b8;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0.5rem 0 0.25rem;
}

h4:first-child {
  margin-top: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: #cbd5e1;
  padding: 0.1rem 0;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.line {
  width: 16px;
  height: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}
</style>
