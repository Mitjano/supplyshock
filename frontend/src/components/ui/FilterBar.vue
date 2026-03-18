<template>
  <div class="ss-filter-bar">
    <!-- Commodity selector -->
    <div class="filter-group">
      <label class="filter-label">Commodity</label>
      <select v-model="localCommodity" class="ss-select" @change="emitChange">
        <option value="">All</option>
        <option v-for="c in commodities" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>
    </div>

    <!-- Region selector -->
    <div class="filter-group">
      <label class="filter-label">Region</label>
      <select v-model="localRegion" class="ss-select" @change="emitChange">
        <option value="">All</option>
        <option v-for="r in regions" :key="r.value" :value="r.value">
          {{ r.label }}
        </option>
      </select>
    </div>

    <!-- Date range -->
    <div class="filter-group">
      <label class="filter-label">From</label>
      <input
        v-model="localDateFrom"
        type="date"
        class="ss-input"
        @change="emitChange"
      />
    </div>
    <div class="filter-group">
      <label class="filter-label">To</label>
      <input
        v-model="localDateTo"
        type="date"
        class="ss-input"
        @change="emitChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, type PropType } from 'vue'

export interface SelectOption {
  value: string
  label: string
}

export interface FilterState {
  commodity: string
  region: string
  dateFrom: string
  dateTo: string
}

const props = defineProps({
  commodities: {
    type: Array as PropType<SelectOption[]>,
    default: () => [
      { value: 'crude_oil', label: 'Crude Oil' },
      { value: 'natural_gas', label: 'Natural Gas' },
      { value: 'gold', label: 'Gold' },
      { value: 'copper', label: 'Copper' },
      { value: 'wheat', label: 'Wheat' },
      { value: 'corn', label: 'Corn' },
    ],
  },
  regions: {
    type: Array as PropType<SelectOption[]>,
    default: () => [
      { value: 'north_america', label: 'North America' },
      { value: 'europe', label: 'Europe' },
      { value: 'asia', label: 'Asia' },
      { value: 'middle_east', label: 'Middle East' },
      { value: 'africa', label: 'Africa' },
      { value: 'south_america', label: 'South America' },
    ],
  },
  initialCommodity: { type: String, default: '' },
  initialRegion: { type: String, default: '' },
  initialDateFrom: { type: String, default: '' },
  initialDateTo: { type: String, default: '' },
})

const emit = defineEmits<{
  (e: 'filter-change', filters: FilterState): void
}>()

const localCommodity = ref(props.initialCommodity)
const localRegion = ref(props.initialRegion)
const localDateFrom = ref(props.initialDateFrom)
const localDateTo = ref(props.initialDateTo)

function emitChange() {
  emit('filter-change', {
    commodity: localCommodity.value,
    region: localRegion.value,
    dateFrom: localDateFrom.value,
    dateTo: localDateTo.value,
  })
}
</script>

<style scoped>
.ss-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ss-space-lg, 16px);
  align-items: flex-end;
  padding: var(--ss-space-md, 12px) 0;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: var(--ss-space-xs, 4px);
}

.filter-label {
  color: var(--ss-text-muted, #94a3b8);
  font-size: var(--ss-text-xs, 0.75rem);
  font-weight: var(--ss-font-medium, 500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ss-select,
.ss-input {
  background: var(--ss-bg-surface, #334155);
  border: 1px solid var(--ss-border, #475569);
  border-radius: var(--ss-radius-md, 6px);
  color: var(--ss-text-primary, #f8fafc);
  font-size: var(--ss-text-sm, 0.875rem);
  padding: var(--ss-space-sm, 8px) var(--ss-space-md, 12px);
  outline: none;
  transition: border-color var(--ss-transition-fast, 150ms ease);
  min-width: 140px;
}

.ss-select:focus,
.ss-input:focus {
  border-color: var(--ss-accent, #3b82f6);
}

/* Dark date input icon */
.ss-input[type="date"]::-webkit-calendar-picker-indicator {
  filter: invert(0.7);
}
</style>
