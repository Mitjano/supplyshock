<template>
  <div class="infrastructure-controls">
    <button
      class="toggle-btn"
      :class="{ active: showInfrastructure }"
      @click="toggleInfrastructure"
      :title="showInfrastructure ? 'Hide infrastructure' : 'Show infrastructure'"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 14V6l6-4 6 4v8H2z" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <rect x="6" y="9" width="4" height="5" stroke="currentColor" stroke-width="1" fill="none"/>
      </svg>
      <span>Infrastructure</span>
    </button>

    <div v-if="showInfrastructure" class="type-filters">
      <button
        v-for="(cfg, typeKey) in infraTypes"
        :key="typeKey"
        class="type-chip"
        :class="{ active: activeTypes.has(typeKey) }"
        :style="activeTypes.has(typeKey) ? { borderColor: cfg.color, color: cfg.color } : {}"
        @click="toggleType(typeKey)"
      >
        <span class="chip-dot" :style="{ background: cfg.color }"></span>
        {{ cfg.label }}
      </button>
    </div>
  </div>

  <!-- Popups rendered via map library — this is data-only -->
  <teleport to="body">
    <div v-if="selectedAsset" class="infra-popup" :style="popupStyle">
      <button class="popup-close" @click="selectedAsset = null">&times;</button>
      <h3>{{ selectedAsset.name }}</h3>
      <div class="popup-row">
        <span class="popup-label">Type</span>
        <span class="popup-value" :style="{ color: infraTypes[selectedAsset.type]?.color || '#94a3b8' }">
          {{ infraTypes[selectedAsset.type]?.label || selectedAsset.type }}
        </span>
      </div>
      <div class="popup-row" v-if="selectedAsset.capacity">
        <span class="popup-label">Capacity</span>
        <span class="popup-value">{{ selectedAsset.capacity }} {{ selectedAsset.capacity_unit }}</span>
      </div>
      <div class="popup-row">
        <span class="popup-label">Country</span>
        <span class="popup-value">{{ selectedAsset.country_code }}</span>
      </div>
      <div class="popup-row">
        <span class="popup-label">Status</span>
        <span class="popup-value" :class="'status-' + selectedAsset.status">{{ selectedAsset.status }}</span>
      </div>
      <div class="popup-row" v-if="selectedAsset.commodities?.length">
        <span class="popup-label">Commodities</span>
        <span class="popup-value">{{ selectedAsset.commodities.join(', ').replace(/_/g, ' ') }}</span>
      </div>
      <p v-if="selectedAsset.description" class="popup-desc">{{ selectedAsset.description }}</p>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useApi } from '../../composables/useApi'
import { useMapStore } from '../../stores/useMapStore'

interface InfraAsset {
  id: string
  type: string
  name: string
  latitude: number
  longitude: number
  status: string
  capacity: number | null
  capacity_unit: string | null
  commodities: string[]
  country_code: string
  description: string | null
}

const infraTypes: Record<string, { label: string; color: string }> = {
  pipeline: { label: 'Pipelines', color: '#6b7280' },
  refinery: { label: 'Refineries', color: '#f97316' },
  lng_terminal: { label: 'LNG Terminals', color: '#22c55e' },
  coal_port: { label: 'Coal Ports', color: '#92400e' },
  oil_field: { label: 'Oil Fields', color: '#ef4444' },
  storage: { label: 'Storage', color: '#3b82f6' },
}

const { get } = useApi()
const mapStore = useMapStore()

const showInfrastructure = ref(false)
const assets = ref<InfraAsset[]>([])
const activeTypes = ref<Set<string>>(new Set(Object.keys(infraTypes)))
const selectedAsset = ref<InfraAsset | null>(null)
const loading = ref(false)
const popupPosition = ref<{ x: number; y: number }>({ x: 0, y: 0 })

const popupStyle = computed(() => ({
  left: `${popupPosition.value.x}px`,
  top: `${popupPosition.value.y}px`,
}))

const filteredAssets = computed(() => {
  return assets.value.filter(a => activeTypes.value.has(a.type))
})

async function toggleInfrastructure() {
  showInfrastructure.value = !showInfrastructure.value
  if (showInfrastructure.value && assets.value.length === 0) {
    await fetchInfrastructure()
  }
}

function toggleType(type: string) {
  if (activeTypes.value.has(type)) {
    activeTypes.value.delete(type)
  } else {
    activeTypes.value.add(type)
  }
  // Trigger reactivity
  activeTypes.value = new Set(activeTypes.value)
}

async function fetchInfrastructure(bbox?: string) {
  loading.value = true
  try {
    const params: Record<string, string> = { limit: '500' }
    if (bbox) params.bbox = bbox
    const body = await get<{ data: InfraAsset[] }>('/infrastructure', params)
    assets.value = body.data
  } catch (e) {
    console.error('Failed to fetch infrastructure:', e)
  } finally {
    loading.value = false
  }
}

function selectAsset(asset: InfraAsset, screenX?: number, screenY?: number) {
  selectedAsset.value = asset
  if (screenX !== undefined && screenY !== undefined) {
    popupPosition.value = { x: screenX, y: screenY }
  }
}

// Expose for parent map component to call on viewport change
defineExpose({
  assets: filteredAssets,
  showInfrastructure,
  infraTypes,
  fetchInfrastructure,
  selectAsset,
  selectedAsset,
})
</script>

<style scoped>
.infrastructure-controls {
  position: absolute;
  top: 1rem;
  left: 1rem;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover {
  border-color: #475569;
  color: #e2e8f0;
}

.toggle-btn.active {
  border-color: #3b82f6;
  color: #e2e8f0;
  background: rgba(59, 130, 246, 0.15);
}

.type-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  max-width: 280px;
}

.type-chip {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid #334155;
  border-radius: 4px;
  color: #64748b;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}

.type-chip.active {
  background: rgba(15, 23, 42, 0.95);
}

.type-chip:hover {
  border-color: #475569;
}

.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.infra-popup {
  position: fixed;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1rem;
  min-width: 240px;
  max-width: 320px;
  z-index: 1000;
  color: #e2e8f0;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.popup-close {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  color: #64748b;
  font-size: 1.2rem;
  cursor: pointer;
}

.popup-close:hover {
  color: #e2e8f0;
}

.infra-popup h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  color: #f8fafc;
}

.popup-row {
  display: flex;
  justify-content: space-between;
  padding: 0.2rem 0;
  font-size: 0.8rem;
}

.popup-label {
  color: #64748b;
}

.popup-value {
  color: #cbd5e1;
  font-weight: 500;
}

.status-operational {
  color: #22c55e;
}

.status-maintenance {
  color: #f59e0b;
}

.status-offline {
  color: #ef4444;
}

.popup-desc {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #94a3b8;
  line-height: 1.4;
}
</style>
