<template>
  <div class="conflict-layer-controls">
    <button class="toggle-btn" :class="{ active: visible }" @click="toggle">
      <i class="pi pi-exclamation-circle" />
      {{ t('analytics.conflicts.toggle') }}
      <span v-if="events.length" class="event-count">{{ events.length }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@clerk/vue'

const { t } = useI18n()
const { getToken } = useAuth()
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const props = defineProps<{ map: any }>()

const visible = ref(false)
const events = ref<ConflictEvent[]>([])
let markers: any[] = []

interface ConflictEvent {
  id: string
  lat: number
  lng: number
  event_type: string
  description: string
  date: string
  fatalities: number
  country: string
  source: string
}

async function fetchConflicts() {
  try {
    const token = await getToken.value()
    const resp = await fetch(
      `${API_BASE}/api/v1/risk/conflicts`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!resp.ok) throw new Error(`${resp.status}`)
    const json = await resp.json()
    events.value = json.data || []
  } catch {
    console.error('Failed to fetch conflict events')
  }
}

function toggle() {
  visible.value = !visible.value
}

function addMarkers() {
  if (!props.map || typeof props.map.addLayer !== 'function') return
  removeMarkers()

  // Expects Mapbox GL or Leaflet-like API
  for (const ev of events.value) {
    const el = document.createElement('div')
    el.className = 'conflict-marker'
    el.style.cssText = 'width:12px;height:12px;background:#ef4444;border-radius:50%;border:2px solid rgba(239,68,68,0.4);cursor:pointer;box-shadow:0 0 6px rgba(239,68,68,0.5);'

    const popup = `
      <div style="font-size:0.8rem;max-width:220px;">
        <strong>${ev.event_type}</strong><br/>
        <span style="color:#94a3b8;">${ev.date} — ${ev.country}</span><br/>
        <p style="margin:0.3rem 0;">${ev.description}</p>
        ${ev.fatalities > 0 ? `<span style="color:#ef4444;">Fatalities: ${ev.fatalities}</span><br/>` : ''}
        <span style="color:#64748b;font-size:0.7rem;">Source: ${ev.source}</span>
      </div>
    `

    try {
      // Mapbox GL JS style
      if (props.map.addLayer && (window as any).mapboxgl) {
        const mapboxgl = (window as any).mapboxgl
        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([ev.lng, ev.lat])
          .setPopup(new mapboxgl.Popup({ offset: 10, maxWidth: '250px' }).setHTML(popup))
          .addTo(props.map)
        markers.push(marker)
      }
      // Leaflet fallback
      else if (props.map.addLayer && (window as any).L) {
        const L = (window as any).L
        const icon = L.divIcon({ html: el.outerHTML, className: '', iconSize: [12, 12] })
        const marker = L.marker([ev.lat, ev.lng], { icon }).bindPopup(popup).addTo(props.map)
        markers.push(marker)
      }
    } catch {
      // silently skip if map API unavailable
    }
  }
}

function removeMarkers() {
  for (const m of markers) {
    try { m.remove() } catch { /* noop */ }
  }
  markers = []
}

watch(visible, (val) => {
  if (val) addMarkers()
  else removeMarkers()
})

watch(() => events.value.length, () => {
  if (visible.value) addMarkers()
})

onMounted(() => fetchConflicts())
onUnmounted(() => removeMarkers())
</script>

<style scoped>
.conflict-layer-controls { display: inline-flex; }
.toggle-btn {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 0.4rem 0.75rem; border-radius: var(--ss-radius, 8px);
  border: 1px solid var(--ss-border-light, #2a2a3e);
  background: var(--ss-bg-surface, #1e293b); color: var(--ss-text-secondary, #94a3b8);
  font-size: 0.8rem; cursor: pointer; transition: all 0.2s;
}
.toggle-btn:hover { background: var(--ss-bg-elevated, #334155); }
.toggle-btn.active { background: rgba(239,68,68,0.15); color: #ef4444; border-color: rgba(239,68,68,0.3); }
.event-count {
  background: #ef4444; color: white; font-size: 0.65rem; font-weight: 700;
  padding: 0.05rem 0.35rem; border-radius: 9999px; min-width: 16px; text-align: center;
}
</style>
