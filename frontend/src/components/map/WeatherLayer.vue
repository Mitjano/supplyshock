<template>
  <div class="weather-layer-controls">
    <button
      :class="['weather-toggle', { active: visible }]"
      @click="toggleWeather"
      :title="t('weather.toggle')"
    >
      <i class="pi pi-cloud" />
      <span class="toggle-label">{{ t('weather.title') }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMapStore } from '../../stores/useMapStore'
import { useAuthStore } from '../../stores/useAuthStore'

const { t } = useI18n()
const mapStore = useMapStore()

const visible = ref(false)
const weatherData = ref<any[]>([])
const loading = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let weatherMarkers: any[] = []

const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function getHeaders(): Promise<Record<string, string>> {
  const auth = useAuthStore()
  const token = await auth.getToken()
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' }
}

function toggleWeather() {
  visible.value = !visible.value
  if (!visible.value) {
    clearMarkers()
  }
}

async function fetchWeather() {
  if (!visible.value || !mapStore.map) return

  const bounds = mapStore.map.getBounds()
  if (!bounds) return

  const sw = bounds.getSouthWest()
  const ne = bounds.getNorthEast()
  const bbox = `${sw.lat.toFixed(2)},${sw.lng.toFixed(2)},${ne.lat.toFixed(2)},${ne.lng.toFixed(2)}`

  loading.value = true
  try {
    const headers = await getHeaders()
    const res = await fetch(`${apiBase}/api/v1/weather?bbox=${bbox}`, { headers })
    if (!res.ok) return
    const body = await res.json()
    weatherData.value = body.data || []
    renderMarkers()
  } catch (e) {
    console.error('Failed to fetch weather:', e)
  } finally {
    loading.value = false
  }
}

function debouncedFetch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchWeather, 800)
}

function clearMarkers() {
  if (!mapStore.map) return
  for (const m of weatherMarkers) {
    mapStore.map.removeLayer(m)
  }
  weatherMarkers = []
}

function renderMarkers() {
  clearMarkers()
  if (!mapStore.map || !visible.value) return

  // Dynamic Leaflet import (already available via MapView)
  const L = (window as any).L
  if (!L) return

  for (const pt of weatherData.value) {
    if (pt.wave_height == null) continue

    // Wave height color
    let color = '#22c55e' // green < 1m
    if (pt.wave_height >= 5) color = '#ef4444'      // red > 5m
    else if (pt.wave_height >= 3) color = '#f97316'  // orange 3-5m
    else if (pt.wave_height >= 1) color = '#eab308'  // yellow 1-3m

    const size = Math.max(8, Math.min(20, pt.wave_height * 3))

    const icon = L.divIcon({
      className: 'weather-marker',
      html: `<div style="
        width: ${size}px;
        height: ${size}px;
        background: ${color};
        border-radius: 50%;
        opacity: 0.7;
        border: 1px solid rgba(255,255,255,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 7px;
        color: #fff;
        font-weight: 700;
      ">${pt.wave_height.toFixed(1)}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    })

    const marker = L.marker([pt.lat, pt.lon], { icon, interactive: true })
    marker.bindTooltip(
      `${t('weather.waveHeight')}: ${pt.wave_height.toFixed(1)}m` +
      (pt.wave_period ? `<br>${t('weather.wavePeriod')}: ${pt.wave_period.toFixed(1)}s` : '') +
      (pt.wave_direction != null ? `<br>${t('weather.waveDirection')}: ${pt.wave_direction.toFixed(0)}°` : ''),
      { className: 'weather-tooltip' }
    )
    marker.addTo(mapStore.map)
    weatherMarkers.push(marker)

    // Wind arrow (wave direction as proxy)
    if (pt.wave_direction != null) {
      const arrowIcon = L.divIcon({
        className: 'wind-arrow-marker',
        html: `<div style="
          transform: rotate(${pt.wave_direction}deg);
          font-size: 14px;
          color: ${color};
          opacity: 0.6;
          text-shadow: 0 0 2px rgba(0,0,0,0.5);
        ">&#8593;</div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      })
      const arrowMarker = L.marker([pt.lat + 0.3, pt.lon + 0.3], { icon: arrowIcon, interactive: false })
      arrowMarker.addTo(mapStore.map)
      weatherMarkers.push(arrowMarker)
    }
  }
}

// Watch map movement when visible
watch(visible, (v) => {
  if (v) {
    fetchWeather()
    mapStore.map?.on('moveend', debouncedFetch)
  } else {
    mapStore.map?.off('moveend', debouncedFetch)
  }
})

onUnmounted(() => {
  clearMarkers()
  if (debounceTimer) clearTimeout(debounceTimer)
  mapStore.map?.off('moveend', debouncedFetch)
})
</script>

<style scoped>
.weather-layer-controls {
  position: absolute;
  bottom: 2rem;
  left: 1rem;
  z-index: 10;
}

.weather-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.weather-toggle:hover {
  border-color: #3b82f6;
  color: #e2e8f0;
}

.weather-toggle.active {
  background: rgba(20, 184, 166, 0.15);
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

.toggle-label {
  font-weight: 500;
}
</style>

<style>
/* Global styles for weather markers */
.weather-marker {
  background: transparent !important;
  border: none !important;
}

.wind-arrow-marker {
  background: transparent !important;
  border: none !important;
}

.weather-tooltip {
  background: rgba(15, 23, 42, 0.95) !important;
  border: 1px solid #334155 !important;
  color: #e2e8f0 !important;
  border-radius: 6px !important;
  font-size: 0.8rem !important;
  padding: 0.4rem 0.6rem !important;
}

.weather-tooltip::before {
  border-top-color: rgba(15, 23, 42, 0.95) !important;
}
</style>
