<template>
  <Teleport to="body">
    <Transition name="search-fade">
      <div v-if="open" class="search-overlay" @click.self="close">
        <div class="search-modal">
          <!-- Input -->
          <div class="search-input-wrap">
            <i class="pi pi-search search-icon" />
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              :placeholder="t('search.placeholder')"
              class="search-input"
              @keydown.escape="close"
              @keydown.down.prevent="moveSelection(1)"
              @keydown.up.prevent="moveSelection(-1)"
              @keydown.enter.prevent="selectCurrent"
            />
            <kbd class="search-kbd">ESC</kbd>
          </div>

          <!-- Results -->
          <div v-if="query.length > 0" class="search-results">
            <div v-if="loading" class="search-loading">
              <i class="pi pi-spin pi-spinner" /> {{ t('common.loading') }}
            </div>

            <template v-else-if="totalResults > 0">
              <!-- Vessels -->
              <div v-if="results.vessels.length" class="result-group">
                <div class="result-group-title">
                  <i class="pi pi-compass" /> {{ t('search.vessels') }}
                </div>
                <button
                  v-for="(v, i) in results.vessels"
                  :key="`v-${v.mmsi}`"
                  class="result-item"
                  :class="{ active: flatIndex('vessels', i) === selectedIndex }"
                  @click="goToVessel(v)"
                  @mouseenter="selectedIndex = flatIndex('vessels', i)"
                >
                  <span class="result-name">{{ v.name || `MMSI ${v.mmsi}` }}</span>
                  <span class="result-meta">{{ v.type }} &middot; {{ v.mmsi }}</span>
                </button>
              </div>

              <!-- Ports -->
              <div v-if="results.ports.length" class="result-group">
                <div class="result-group-title">
                  <i class="pi pi-map-marker" /> {{ t('search.ports') }}
                </div>
                <button
                  v-for="(p, i) in results.ports"
                  :key="`p-${p.id}`"
                  class="result-item"
                  :class="{ active: flatIndex('ports', i) === selectedIndex }"
                  @click="goToPort(p)"
                  @mouseenter="selectedIndex = flatIndex('ports', i)"
                >
                  <span class="result-name">{{ p.name }}</span>
                  <span class="result-meta">{{ p.country_code }}{{ p.is_major ? ' (Major)' : '' }}</span>
                </button>
              </div>

              <!-- Chokepoints -->
              <div v-if="results.chokepoints.length" class="result-group">
                <div class="result-group-title">
                  <i class="pi pi-exclamation-triangle" /> {{ t('search.chokepoints') }}
                </div>
                <button
                  v-for="(c, i) in results.chokepoints"
                  :key="`c-${c.id}`"
                  class="result-item"
                  :class="{ active: flatIndex('chokepoints', i) === selectedIndex }"
                  @click="goToChokepoint(c)"
                  @mouseenter="selectedIndex = flatIndex('chokepoints', i)"
                >
                  <span class="result-name">{{ c.name }}</span>
                  <span class="result-meta">{{ c.baseline_risk }}</span>
                </button>
              </div>

              <!-- Commodities -->
              <div v-if="results.commodities.length" class="result-group">
                <div class="result-group-title">
                  <i class="pi pi-chart-line" /> {{ t('search.commodities') }}
                </div>
                <button
                  v-for="(cm, i) in results.commodities"
                  :key="`cm-${cm.commodity}`"
                  class="result-item"
                  :class="{ active: flatIndex('commodities', i) === selectedIndex }"
                  @click="goToCommodity(cm)"
                  @mouseenter="selectedIndex = flatIndex('commodities', i)"
                >
                  <span class="result-name">{{ cm.commodity.replace(/_/g, ' ') }}</span>
                  <span class="result-meta">{{ cm.benchmark }}</span>
                </button>
              </div>
            </template>

            <div v-else-if="!loading && query.length >= 2" class="search-empty">
              {{ t('search.noResults') }}
            </div>
          </div>

          <!-- Recent searches -->
          <div v-else-if="recentSearches.length > 0" class="search-results">
            <div class="result-group">
              <div class="result-group-title">
                <i class="pi pi-clock" /> {{ t('search.recent') }}
              </div>
              <button
                v-for="(r, i) in recentSearches"
                :key="`recent-${i}`"
                class="result-item"
                @click="query = r"
              >
                <span class="result-name">{{ r }}</span>
              </button>
            </div>
          </div>

          <!-- Footer -->
          <div class="search-footer">
            <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> {{ t('search.navigate') }}</span>
            <span><kbd>Enter</kbd> {{ t('search.select') }}</span>
            <span><kbd>Esc</kbd> {{ t('search.close') }}</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useApi } from '@/composables/useApi'
import { useLocalePath } from '@/composables/useLocalePath'

const { t } = useI18n()
const router = useRouter()
const api = useApi()
const { localePath } = useLocalePath()

const open = ref(false)
const query = ref('')
const loading = ref(false)
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

interface SearchResults {
  vessels: { mmsi: number; name: string; type: string; imo: number }[]
  ports: { id: string; name: string; country_code: string; latitude: number; longitude: number; is_major: boolean }[]
  chokepoints: { id: string; slug: string; name: string; latitude: number; longitude: number; baseline_risk: string }[]
  commodities: { commodity: string; benchmark: string }[]
}

const results = ref<SearchResults>({
  vessels: [],
  ports: [],
  chokepoints: [],
  commodities: [],
})

const recentSearches = ref<string[]>(
  JSON.parse(localStorage.getItem('ss-recent-searches') || '[]')
)

const totalResults = computed(() =>
  results.value.vessels.length +
  results.value.ports.length +
  results.value.chokepoints.length +
  results.value.commodities.length
)

const flatItems = computed(() => [
  ...results.value.vessels.map((v, i) => ({ type: 'vessels' as const, index: i, item: v })),
  ...results.value.ports.map((p, i) => ({ type: 'ports' as const, index: i, item: p })),
  ...results.value.chokepoints.map((c, i) => ({ type: 'chokepoints' as const, index: i, item: c })),
  ...results.value.commodities.map((cm, i) => ({ type: 'commodities' as const, index: i, item: cm })),
])

function flatIndex(group: string, i: number): number {
  const order = ['vessels', 'ports', 'chokepoints', 'commodities']
  let offset = 0
  for (const g of order) {
    if (g === group) return offset + i
    offset += results.value[g as keyof SearchResults].length
  }
  return offset + i
}

// Debounced search
let searchTimeout: ReturnType<typeof setTimeout>
watch(query, (val) => {
  clearTimeout(searchTimeout)
  selectedIndex.value = 0

  if (val.length < 2) {
    results.value = { vessels: [], ports: [], chokepoints: [], commodities: [] }
    return
  }

  loading.value = true
  searchTimeout = setTimeout(async () => {
    try {
      const res = await api.get<{ results: SearchResults }>('/search', { q: val })
      results.value = res.results
    } catch {
      results.value = { vessels: [], ports: [], chokepoints: [], commodities: [] }
    } finally {
      loading.value = false
    }
  }, 300)
})

function moveSelection(delta: number) {
  const max = totalResults.value
  if (max === 0) return
  selectedIndex.value = (selectedIndex.value + delta + max) % max
}

function selectCurrent() {
  const item = flatItems.value[selectedIndex.value]
  if (!item) return

  if (item.type === 'vessels') goToVessel(item.item as SearchResults['vessels'][0])
  else if (item.type === 'ports') goToPort(item.item as SearchResults['ports'][0])
  else if (item.type === 'chokepoints') goToChokepoint(item.item as SearchResults['chokepoints'][0])
  else if (item.type === 'commodities') goToCommodity(item.item as SearchResults['commodities'][0])
}

function saveRecent() {
  if (query.value.length < 2) return
  const searches = recentSearches.value.filter(s => s !== query.value)
  searches.unshift(query.value)
  recentSearches.value = searches.slice(0, 5)
  localStorage.setItem('ss-recent-searches', JSON.stringify(recentSearches.value))
}

function goToVessel(v: SearchResults['vessels'][0]) {
  saveRecent()
  close()
  router.push({ path: localePath('/map'), query: { mmsi: String(v.mmsi) } })
}

function goToPort(p: SearchResults['ports'][0]) {
  saveRecent()
  close()
  router.push({ path: localePath('/map'), query: { lat: String(p.latitude), lng: String(p.longitude), zoom: '12' } })
}

function goToChokepoint(c: SearchResults['chokepoints'][0]) {
  saveRecent()
  close()
  router.push({ path: localePath('/bottlenecks'), query: { slug: c.slug } })
}

function goToCommodity(cm: SearchResults['commodities'][0]) {
  saveRecent()
  close()
  router.push({ path: localePath('/commodities'), query: { commodity: cm.commodity } })
}

function close() {
  open.value = false
  query.value = ''
  results.value = { vessels: [], ports: [], chokepoints: [], commodities: [] }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    open.value = !open.value
    if (open.value) {
      nextTick(() => inputRef.value?.focus())
    }
  }
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))

// Expose open method for external use
defineExpose({ open: () => { open.value = true; nextTick(() => inputRef.value?.focus()) } })
</script>

<style scoped>
.search-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 15vh;
}

.search-modal {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg, 12px);
  box-shadow: var(--ss-shadow-lg);
  width: 100%;
  max-width: 640px;
  overflow: hidden;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--ss-border-light);
}

.search-icon {
  color: var(--ss-text-muted);
  font-size: 1.1rem;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--ss-text-primary);
  font-size: 1rem;
}

.search-input::placeholder {
  color: var(--ss-text-muted);
}

.search-kbd {
  background: var(--ss-bg-elevated);
  color: var(--ss-text-muted);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-family: inherit;
  border: 1px solid var(--ss-border-light);
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
  padding: 0.5rem 0;
}

.search-loading,
.search-empty {
  padding: 2rem;
  text-align: center;
  color: var(--ss-text-muted);
  font-size: 0.9rem;
}

.result-group {
  margin-bottom: 0.25rem;
}

.result-group-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1.25rem 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ss-text-muted);
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.6rem 1.25rem;
  background: none;
  border: none;
  color: var(--ss-text-primary);
  font-size: 0.875rem;
  cursor: pointer;
  text-align: left;
  transition: background var(--ss-transition-fast);
}

.result-item:hover,
.result-item.active {
  background: var(--ss-accent-dim);
}

.result-name {
  font-weight: 500;
  text-transform: capitalize;
}

.result-meta {
  color: var(--ss-text-muted);
  font-size: 0.8rem;
}

.search-footer {
  display: flex;
  gap: 1.5rem;
  padding: 0.6rem 1.25rem;
  border-top: 1px solid var(--ss-border-light);
  font-size: 0.75rem;
  color: var(--ss-text-muted);
}

.search-footer kbd {
  background: var(--ss-bg-elevated);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-size: 0.7rem;
  border: 1px solid var(--ss-border-light);
  margin-right: 0.25rem;
}

/* Transition */
.search-fade-enter-active,
.search-fade-leave-active {
  transition: opacity 0.15s ease;
}
.search-fade-enter-from,
.search-fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .search-overlay {
    padding-top: 5vh;
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
