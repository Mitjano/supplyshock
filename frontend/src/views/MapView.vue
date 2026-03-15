<template>
  <div class="map-page">
    <div ref="mapContainer" class="map-container"></div>

    <!-- Filters -->
    <MapFilters />

    <!-- Legend -->
    <MapLegend />

    <!-- Vessel popup -->
    <VesselPopup v-if="mapStore.selectedVessel" />

    <!-- Right panel -->
    <RightPanel />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useMapStore } from '../stores/useMapStore'
import { useAuthStore } from '../stores/useAuthStore'
import VesselPopup from '../components/map/VesselPopup.vue'
import MapLegend from '../components/map/MapLegend.vue'
import MapFilters from '../components/map/MapFilters.vue'
import RightPanel from '../components/map/RightPanel.vue'

const mapStore = useMapStore()
const auth = useAuthStore()
const mapContainer = ref<HTMLElement | null>(null)
let map: maplibregl.Map | null = null
let refreshInterval: ReturnType<typeof setInterval> | null = null

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

function initMap() {
  if (!mapContainer.value) return

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [
        {
          id: 'osm-tiles',
          type: 'raster',
          source: 'osm',
          minzoom: 0,
          maxzoom: 19,
        },
      ],
    },
    center: [30, 20],
    zoom: 2.5,
  })

  map.addControl(new maplibregl.NavigationControl(), 'top-left')

  map.on('load', () => {
    addVesselLayer()
    addPortLayer()
    addTradeFlowLayer()
    loadData()
  })

  map.on('click', 'vessels-layer', (e) => {
    const feature = e.features?.[0]
    if (feature?.properties?.mmsi) {
      mapStore.selectVessel(feature.properties.mmsi)
    }
  })

  map.on('mouseenter', 'vessels-layer', () => {
    if (map) map.getCanvas().style.cursor = 'pointer'
  })
  map.on('mouseleave', 'vessels-layer', () => {
    if (map) map.getCanvas().style.cursor = ''
  })
}

function addVesselLayer() {
  if (!map) return

  map.addSource('vessels', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })

  map.addLayer({
    id: 'vessels-layer',
    type: 'circle',
    source: 'vessels',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 2, 8, 5],
      'circle-color': [
        'match', ['get', 'vessel_type'],
        'tanker', VESSEL_TYPE_COLORS.tanker,
        'bulk_carrier', VESSEL_TYPE_COLORS.bulk_carrier,
        'container', VESSEL_TYPE_COLORS.container,
        'lng_carrier', VESSEL_TYPE_COLORS.lng_carrier,
        VESSEL_TYPE_COLORS.other,
      ],
      'circle-opacity': 0.8,
      'circle-stroke-width': 1,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-opacity': 0.4,
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
      'circle-radius': 6,
      'circle-color': '#8b5cf6',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
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
    },
  })
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
  await Promise.all([
    mapStore.fetchVessels(),
    mapStore.fetchPorts(),
    mapStore.fetchTradeFlows(),
  ])
  updateVesselSource()
  updatePortSource()
  updateTradeFlowSource()
}

onMounted(() => {
  initMap()
  // Refresh vessels every 30 seconds
  refreshInterval = setInterval(async () => {
    if (auth.isAuthenticated) {
      await mapStore.fetchVessels()
      updateVesselSource()
    }
  }, 30_000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
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
</style>
