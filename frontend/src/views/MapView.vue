<template>
  <div class="map-page">
    <div ref="mapContainer" class="map-container"></div>

    <!-- Loading overlay -->
    <Transition name="fade">
      <div v-if="isInitialLoading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">{{ t('map.loading') }}</div>
      </div>
    </Transition>

    <!-- Error toast -->
    <Transition name="slide-toast">
      <div v-if="errorMessage" class="error-toast" @click="errorMessage = null">
        <i class="pi pi-exclamation-triangle"></i>
        <span>{{ errorMessage }}</span>
        <button class="toast-close" @click.stop="errorMessage = null">&times;</button>
      </div>
    </Transition>

    <!-- Status bar -->
    <div class="status-bar">
      <span class="vessel-count">
        <i class="pi pi-map-marker"></i>
        {{ t('map.vesselCount', { count: mapStore.filteredVessels.length }) }}
      </span>
      <span v-if="secondsAgo !== null" class="last-updated">
        {{ t('map.lastUpdated', { seconds: secondsAgo }) }}
      </span>
    </div>

    <!-- Filters -->
    <MapFilters />

    <!-- Legend -->
    <MapLegend />

    <!-- Vessel popup -->
    <VesselPopup
      v-if="mapStore.selectedVessel"
      @view-trail="onViewTrail"
      @hide-trail="onHideTrail"
      :trail-visible="trailVisible"
    />

    <!-- Weather layer -->
    <WeatherLayer />

    <!-- Right panel -->
    <RightPanel />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useI18n } from 'vue-i18n'
import { useMapStore } from '../stores/useMapStore'
import { useAuthStore } from '../stores/useAuthStore'
import VesselPopup from '../components/map/VesselPopup.vue'
import MapLegend from '../components/map/MapLegend.vue'
import MapFilters from '../components/map/MapFilters.vue'
import RightPanel from '../components/map/RightPanel.vue'
import WeatherLayer from '../components/map/WeatherLayer.vue'

const { t } = useI18n()
const mapStore = useMapStore()
const auth = useAuthStore()
const mapContainer = ref<HTMLElement | null>(null)
let map: maplibregl.Map | null = null
let refreshInterval: ReturnType<typeof setInterval> | null = null
let tickInterval: ReturnType<typeof setInterval> | null = null

const isInitialLoading = ref(true)
const errorMessage = ref<string | null>(null)
const secondsAgo = ref<number | null>(null)
const trailVisible = ref(false)

const VESSEL_TYPE_COLORS: Record<string, string> = {
  tanker: '#ef4444',
  bulk_carrier: '#f59e0b',
  container: '#3b82f6',
  lng_carrier: '#10b981',
  other: '#6b7280',
}

const COMMODITY_COLORS: Record<string, string> = {
  crude_oil: '#ef4444',
  coal: '#374151',
  iron_ore: '#b45309',
  copper: '#d97706',
  lng: '#10b981',
}

// --- Vessel triangle image generation ---
function createTriangleImage(color: string, size = 24): ImageData {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 2

  // Draw triangle pointing up (rotation handled by icon-rotate)
  ctx.beginPath()
  ctx.moveTo(cx, cy - r)
  ctx.lineTo(cx - r * 0.7, cy + r * 0.6)
  ctx.lineTo(cx + r * 0.7, cy + r * 0.6)
  ctx.closePath()
  ctx.fillStyle = color
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,255,255,0.6)'
  ctx.lineWidth = 1.5
  ctx.stroke()

  return ctx.getImageData(0, 0, size, size)
}

function initMap() {
  if (!mapContainer.value) return

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    center: [30, 20],
    zoom: 2.5,
    attributionControl: false,
  })

  map.addControl(new maplibregl.NavigationControl(), 'top-left')
  map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

  map.on('load', () => {
    registerVesselImages()
    addVesselLayer()
    addVesselLabelLayer()
    addPortLayer()
    addTradeFlowLayer()
    addFloatingStorageLayer()
    loadData()
  })

  map.on('click', 'vessels-layer', (e) => {
    const feature = e.features?.[0]
    if (feature?.properties?.mmsi) {
      mapStore.selectVessel(feature.properties.mmsi)
    }
  })

  map.on('click', 'floating-storage-dot', (e) => {
    const feature = e.features?.[0]
    if (feature?.properties?.mmsi) {
      mapStore.selectVessel(feature.properties.mmsi)
    }
  })

  for (const layerId of ['vessels-layer', 'floating-storage-dot']) {
    map.on('mouseenter', layerId, () => {
      if (map) map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', layerId, () => {
      if (map) map.getCanvas().style.cursor = ''
    })
  }
}

function registerVesselImages() {
  if (!map) return
  const types = Object.entries(VESSEL_TYPE_COLORS)
  for (const [type, color] of types) {
    const img = createTriangleImage(color, 24)
    map.addImage(`vessel-${type}`, img, { sdf: false })
  }
}

function addVesselLayer() {
  if (!map) return

  map.addSource('vessels', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })

  // Symbol layer with directional triangles
  map.addLayer({
    id: 'vessels-layer',
    type: 'symbol',
    source: 'vessels',
    layout: {
      'icon-image': [
        'match', ['get', 'vessel_type'],
        'tanker', 'vessel-tanker',
        'bulk_carrier', 'vessel-bulk_carrier',
        'container', 'vessel-container',
        'lng_carrier', 'vessel-lng_carrier',
        'vessel-other',
      ],
      'icon-size': [
        'interpolate', ['linear'], ['zoom'],
        2, 0.5,
        6, 0.7,
        10, 1.0,
        14, 1.3,
      ],
      'icon-rotate': ['coalesce', ['get', 'heading'], ['get', 'course'], 0],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  })
}

function addVesselLabelLayer() {
  if (!map) return

  map.addLayer({
    id: 'vessel-labels',
    type: 'symbol',
    source: 'vessels',
    minzoom: 10,
    layout: {
      'text-field': ['get', 'vessel_name'],
      'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
      'text-size': 11,
      'text-offset': [0, 1.5],
      'text-anchor': 'top',
      'text-allow-overlap': false,
    },
    paint: {
      'text-color': '#e2e8f0',
      'text-halo-color': 'rgba(0,0,0,0.8)',
      'text-halo-width': 1.5,
    },
  })
}

function addPortLayer() {
  if (!map) return

  map.addSource('ports', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })

  map.addLayer({
    id: 'ports-layer',
    type: 'circle',
    source: 'ports',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 3, 8, 6, 12, 10],
      'circle-color': '#8b5cf6',
      'circle-stroke-width': 2,
      'circle-stroke-color': 'rgba(139, 92, 246, 0.4)',
      'circle-opacity': 0.85,
    },
  })
}

function addTradeFlowLayer() {
  if (!map) return

  map.addSource('trade-flows', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })

  map.addLayer({
    id: 'trade-flows-layer',
    type: 'line',
    source: 'trade-flows',
    paint: {
      'line-color': [
        'match', ['get', 'commodity'],
        'crude_oil', COMMODITY_COLORS.crude_oil,
        'coal', COMMODITY_COLORS.coal,
        'iron_ore', COMMODITY_COLORS.iron_ore,
        'copper', COMMODITY_COLORS.copper,
        'lng', COMMODITY_COLORS.lng,
        '#6b7280',
      ],
      'line-width': ['interpolate', ['linear'], ['get', 'volume_mt'], 0, 1, 500000, 6],
      'line-opacity': 0.5,
      'line-dasharray': [2, 2],
    },
  })
}

function addFloatingStorageLayer() {
  if (!map) return

  map.addSource('floating-storage', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })

  // Pulsing outer ring
  map.addLayer({
    id: 'floating-storage-pulse',
    type: 'circle',
    source: 'floating-storage',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 6, 8, 14, 12, 20],
      'circle-color': 'rgba(251, 146, 60, 0.15)',
      'circle-stroke-width': 1.5,
      'circle-stroke-color': 'rgba(251, 146, 60, 0.4)',
    },
  })

  // Inner dot
  map.addLayer({
    id: 'floating-storage-dot',
    type: 'circle',
    source: 'floating-storage',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 3, 8, 6, 12, 9],
      'circle-color': '#fb923c',
      'circle-stroke-width': 1.5,
      'circle-stroke-color': 'rgba(255, 255, 255, 0.5)',
    },
  })

  // Labels
  map.addLayer({
    id: 'floating-storage-labels',
    type: 'symbol',
    source: 'floating-storage',
    minzoom: 6,
    layout: {
      'text-field': ['get', 'vessel_name'],
      'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
      'text-size': 10,
      'text-offset': [0, 1.8],
      'text-anchor': 'top',
      'text-allow-overlap': false,
    },
    paint: {
      'text-color': '#fb923c',
      'text-halo-color': 'rgba(0,0,0,0.8)',
      'text-halo-width': 1.5,
    },
  })
}

function updateFloatingStorageSource() {
  if (!map) return
  const source = map.getSource('floating-storage') as maplibregl.GeoJSONSource | undefined
  if (!source) return

  // Floating storage voyages have lat/lon from the vessel's last known position
  // We need to cross-reference with vessel positions
  const fsVoyages = mapStore.floatingStorageVessels
  const vesselMap = new Map(mapStore.vessels.map(v => [v.mmsi, v]))

  const features = fsVoyages
    .map(v => {
      const pos = vesselMap.get(v.mmsi)
      if (!pos) return null
      return {
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: [pos.longitude, pos.latitude] },
        properties: {
          mmsi: v.mmsi,
          vessel_name: v.vessel_name || 'Unknown',
          vessel_type: v.vessel_type,
          cargo_type: v.cargo_type,
          volume_estimate: v.volume_estimate,
        },
      }
    })
    .filter(Boolean)

  source.setData({ type: 'FeatureCollection', features: features as any })
}

function updateVesselSource() {
  if (!map) return
  const source = map.getSource('vessels') as maplibregl.GeoJSONSource | undefined
  if (!source) return

  const features = mapStore.filteredVessels.map(v => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: [v.longitude, v.latitude] },
    properties: {
      mmsi: v.mmsi,
      vessel_type: v.vessel_type,
      vessel_name: v.vessel_name || 'Unknown',
      speed_knots: v.speed_knots,
      heading: v.heading ?? v.course ?? 0,
      course: v.course ?? 0,
      dwt: v.dwt ?? 0,
    },
  }))

  source.setData({ type: 'FeatureCollection', features })
}

function updatePortSource() {
  if (!map) return
  const source = map.getSource('ports') as maplibregl.GeoJSONSource | undefined
  if (!source) return

  const features = mapStore.ports.map(p => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: [p.longitude, p.latitude] },
    properties: { name: p.name, commodities: p.commodities.join(', ') },
  }))

  source.setData({ type: 'FeatureCollection', features })
}

function updateTradeFlowSource() {
  if (!map) return
  const source = map.getSource('trade-flows') as maplibregl.GeoJSONSource | undefined
  if (!source) return

  source.setData({ type: 'FeatureCollection', features: mapStore.tradeFlows })
}

async function loadData() {
  if (!auth.isAuthenticated) return
  isInitialLoading.value = true
  try {
    await Promise.all([
      mapStore.fetchVessels(),
      mapStore.fetchPorts(),
      mapStore.fetchTradeFlows(),
      mapStore.fetchVoyages({ status: 'floating_storage' }),
    ])
    updateVesselSource()
    updatePortSource()
    updateTradeFlowSource()
    updateFloatingStorageSource()
  } catch {
    errorMessage.value = t('map.errorLoadingData')
  } finally {
    isInitialLoading.value = false
  }
}

// --- Trail drawing ---
async function onViewTrail(mmsi: number) {
  if (!map) return
  try {
    await mapStore.fetchVesselTrail(mmsi)
    drawTrailOnMap()
    trailVisible.value = true
  } catch {
    errorMessage.value = t('map.loadingTrail')
  }
}

function onHideTrail() {
  removeTrailFromMap()
  trailVisible.value = false
  mapStore.vesselTrail = []
}

function drawTrailOnMap() {
  if (!map || !mapStore.vesselTrail.length) return
  removeTrailFromMap()

  const coordinates = mapStore.vesselTrail.map(p => [p.longitude, p.latitude])

  map.addSource('vessel-trail', {
    type: 'geojson',
    data: {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates },
      properties: {},
    },
  })

  map.addLayer({
    id: 'vessel-trail-layer',
    type: 'line',
    source: 'vessel-trail',
    paint: {
      'line-color': '#38bdf8',
      'line-width': 2.5,
      'line-opacity': 0.8,
      'line-dasharray': [3, 2],
    },
  })

  // Trail dots
  map.addLayer({
    id: 'vessel-trail-dots',
    type: 'circle',
    source: 'vessel-trail',
    paint: {
      'circle-radius': 3,
      'circle-color': '#38bdf8',
      'circle-opacity': 0.6,
    },
  })
}

function removeTrailFromMap() {
  if (!map) return
  if (map.getLayer('vessel-trail-dots')) map.removeLayer('vessel-trail-dots')
  if (map.getLayer('vessel-trail-layer')) map.removeLayer('vessel-trail-layer')
  if (map.getSource('vessel-trail')) map.removeSource('vessel-trail')
}

// Watch for vessel type filter changes
watch(() => mapStore.vesselTypeFilter, () => {
  updateVesselSource()
})

// Update "seconds ago" counter
function updateSecondsAgo() {
  if (mapStore.lastUpdated) {
    secondsAgo.value = Math.floor((Date.now() - mapStore.lastUpdated.getTime()) / 1000)
  }
}

onMounted(() => {
  initMap()
  // Refresh vessels every 30 seconds
  refreshInterval = setInterval(async () => {
    if (auth.isAuthenticated) {
      try {
        await mapStore.fetchVessels()
        updateVesselSource()
      } catch {
        errorMessage.value = t('map.errorLoadingVessels')
      }
    }
  }, 30_000)

  // Tick the seconds-ago counter
  tickInterval = setInterval(updateSecondsAgo, 1000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (tickInterval) clearInterval(tickInterval)
  map?.remove()
})
</script>

<style scoped>
.map-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

/* Loading overlay */
.loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(2, 6, 23, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 200;
  gap: 1rem;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: #94a3b8;
  font-size: 0.9rem;
  letter-spacing: 0.02em;
}

/* Error toast */
.error-toast {
  position: absolute;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(127, 29, 29, 0.95);
  border: 1px solid #991b1b;
  border-radius: 8px;
  padding: 0.75rem 1.25rem;
  color: #fca5a5;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  z-index: 300;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  cursor: pointer;
  max-width: 400px;
}

.error-toast i {
  color: #f87171;
  font-size: 1rem;
  flex-shrink: 0;
}

.toast-close {
  background: none;
  border: none;
  color: #fca5a5;
  font-size: 1.2rem;
  cursor: pointer;
  margin-left: 0.5rem;
  padding: 0;
  line-height: 1;
}

/* Status bar */
.status-bar {
  position: absolute;
  bottom: 0.5rem;
  right: 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
  z-index: 10;
  font-size: 0.75rem;
  color: #64748b;
}

.status-bar .vessel-count {
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.status-bar .last-updated {
  color: #475569;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-toast-enter-active,
.slide-toast-leave-active {
  transition: all 0.3s ease;
}
.slide-toast-enter-from {
  opacity: 0;
  transform: translate(-50%, -20px);
}
.slide-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -20px);
}
</style>
