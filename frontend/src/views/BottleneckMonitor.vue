<template>
  <div class="bottleneck-monitor" :class="{ 'detail-open': !!store.selectedBottleneck }">
    <!-- Left Panel: Bottleneck List -->
    <aside class="list-panel" :class="{ 'mobile-hidden': mobileShowDetail }">
      <header class="panel-header">
        <div class="header-top">
          <h1>{{ t('bottleneck.title') }}</h1>
          <span class="node-count">{{ filteredNodes.length }} {{ t('bottleneck.nodes') }}</span>
        </div>
        <div class="search-wrapper">
          <i class="pi pi-search search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            class="search-input"
            :placeholder="t('common.search')"
          />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
            <i class="pi pi-times" />
          </button>
        </div>
      </header>

      <!-- Loading skeleton -->
      <div v-if="listLoading" class="bottleneck-list">
        <div v-for="i in 6" :key="i" class="node-card skeleton-card">
          <div class="skeleton-line skeleton-title" />
          <div class="skeleton-line skeleton-meta" />
          <div class="skeleton-line skeleton-bar" />
          <div class="skeleton-tags">
            <div class="skeleton-tag" />
            <div class="skeleton-tag" />
          </div>
        </div>
      </div>

      <!-- Error state -->
      <div v-else-if="listError" class="list-error">
        <i class="pi pi-exclamation-triangle error-icon" />
        <p>{{ t('common.error') }}</p>
        <button class="retry-btn" @click="loadBottlenecks">
          <i class="pi pi-refresh" /> {{ t('common.retry') }}
        </button>
      </div>

      <!-- Bottleneck list -->
      <div v-else class="bottleneck-list">
        <div v-if="filteredNodes.length === 0" class="empty-list">
          <i class="pi pi-search" />
          <p>{{ t('bottleneck.noResults') }}</p>
        </div>
        <div
          v-for="node in filteredNodes"
          :key="node.slug"
          :class="['node-card', { selected: store.selectedBottleneck?.slug === node.slug }]"
          @click="handleNodeClick(node.slug)"
        >
          <div class="node-header">
            <span class="node-name">{{ node.name }}</span>
            <span :class="['risk-badge', `risk-${node.risk_level}`]">
              {{ t(`bottleneck.risk.${node.risk_level}`) }}
            </span>
          </div>
          <div class="node-meta">
            <span :class="['type-badge', `type-${node.node_type}`]">
              <i :class="['pi', typeIcon(node.node_type)]" />
              {{ t(`bottleneck.type.${node.node_type}`, node.node_type) }}
            </span>
            <span v-if="node.vessel_count" class="vessel-count">
              <i class="pi pi-send" />
              {{ node.vessel_count }}
            </span>
          </div>
          <div class="risk-bar-container">
            <div
              class="risk-bar"
              :class="`risk-${node.risk_level}`"
              :style="{ width: riskWidth(node.risk_level) }"
            />
            <span class="risk-bar-label">{{ riskNumeric(node.risk_level) }}/10</span>
          </div>
          <div class="commodity-tags">
            <span
              v-for="c in node.commodities?.slice(0, 4)"
              :key="c"
              :class="['tag', `tag-${getCommodityGroup(c)}`]"
            >
              {{ c.replace(/_/g, ' ') }}
            </span>
            <span v-if="(node.commodities?.length || 0) > 4" class="tag tag-more">
              +{{ node.commodities!.length - 4 }}
            </span>
          </div>
        </div>
      </div>

      <!-- Auto-refresh indicator -->
      <div class="refresh-indicator" v-if="!listLoading && !listError">
        <span class="refresh-text">
          {{ t('common.lastUpdated') }}: {{ lastRefreshLabel }}
        </span>
      </div>
    </aside>

    <!-- Right Panel: Detail -->
    <main class="detail-panel" :class="{ 'mobile-visible': mobileShowDetail }">
      <!-- Mobile back button -->
      <button v-if="mobileShowDetail" class="mobile-back" @click="closeDetail">
        <i class="pi pi-arrow-left" />
        {{ t('bottleneck.backToList') }}
      </button>

      <!-- Loading detail skeleton -->
      <div v-if="store.loading" class="detail-loading">
        <div class="skeleton-line skeleton-detail-title" />
        <div class="skeleton-line skeleton-detail-sub" />
        <div class="stats-grid">
          <div v-for="i in 4" :key="i" class="stat-card">
            <div class="skeleton-line skeleton-stat-label" />
            <div class="skeleton-line skeleton-stat-value" />
          </div>
        </div>
        <div class="skeleton-line skeleton-chart" />
      </div>

      <!-- Detail content -->
      <div v-else-if="store.selectedBottleneck" class="detail-content fade-in">
        <button class="close-detail desktop-only" @click="closeDetail">
          <i class="pi pi-times" />
        </button>

        <!-- Header -->
        <div class="detail-header">
          <div>
            <h2>{{ store.selectedBottleneck.name }}</h2>
            <div class="detail-meta">
              <span :class="['type-badge', `type-${store.selectedBottleneck.node_type}`]">
                <i :class="['pi', typeIcon(store.selectedBottleneck.node_type)]" />
                {{ t(`bottleneck.type.${store.selectedBottleneck.node_type}`, store.selectedBottleneck.node_type) }}
              </span>
              <span :class="['risk-badge', `risk-${store.selectedBottleneck.risk_level}`]">
                {{ t(`bottleneck.risk.${store.selectedBottleneck.risk_level}`) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Description -->
        <p v-if="store.selectedBottleneck.throughput_description" class="detail-description">
          {{ store.selectedBottleneck.throughput_description }}
        </p>

        <!-- Stats Grid -->
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon"><i class="pi pi-send" /></div>
            <div class="stat-label">{{ t('bottleneck.stats.vessels') }}</div>
            <div class="stat-value">{{ store.selectedBottleneck.vessel_count ?? '—' }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon"><i class="pi pi-gauge" /></div>
            <div class="stat-label">{{ t('bottleneck.stats.avgSpeed') }}</div>
            <div class="stat-value">
              {{ store.selectedBottleneck.avg_speed?.toFixed(1) ?? '—' }}
              <span class="stat-unit">kn</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon"><i class="pi pi-chart-bar" /></div>
            <div class="stat-label">{{ t('bottleneck.stats.congestion') }}</div>
            <div class="stat-value">
              {{ store.selectedBottleneck.congestion_index?.toFixed(2) ?? '—' }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon risk-icon" :class="`risk-${store.selectedBottleneck.risk_level}`"><i class="pi pi-shield" /></div>
            <div class="stat-label">{{ t('bottleneck.stats.riskLevel') }}</div>
            <div :class="['stat-value', `text-${store.selectedBottleneck.risk_level}`]">
              {{ t(`bottleneck.risk.${store.selectedBottleneck.risk_level}`) }}
            </div>
          </div>
        </div>

        <!-- ECharts Congestion History -->
        <div class="chart-section" v-if="store.selectedBottleneck.status_history?.length">
          <h3>{{ t('bottleneck.history') }}</h3>
          <div ref="chartContainer" class="chart-container" />
        </div>

        <!-- Commodities -->
        <div class="commodities-section" v-if="store.selectedBottleneck.commodities?.length">
          <h3>{{ t('bottleneck.commoditiesAffected') }}</h3>
          <div class="commodity-chips">
            <span
              v-for="c in store.selectedBottleneck.commodities"
              :key="c"
              :class="['commodity-chip', `chip-${getCommodityGroup(c)}`]"
            >
              {{ c.replace(/_/g, ' ') }}
            </span>
          </div>
        </div>

        <!-- Simulation Button -->
        <button class="sim-btn" @click="goToSimulation">
          <i class="pi pi-play" />
          {{ t('bottleneck.runSimulation') }}
        </button>
      </div>

      <!-- Empty state -->
      <div v-else class="empty-detail">
        <div class="empty-illustration">
          <i class="pi pi-map" />
        </div>
        <h3>{{ t('bottleneck.selectPrompt') }}</h3>
        <p>{{ t('bottleneck.selectDescription') }}</p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useBottleneckStore } from '@/stores/useBottleneckStore'
import { useChart } from '@/composables/useChart'
import { useLocalePath } from '@/composables/useLocalePath'

const { t } = useI18n()
const store = useBottleneckStore()
const router = useRouter()
const { localePath } = useLocalePath()

// --- State ---
const searchQuery = ref('')
const listLoading = ref(false)
const listError = ref(false)
const mobileShowDetail = ref(false)
const lastRefreshTime = ref<Date | null>(null)
const lastRefreshLabel = ref('—')

// --- Chart ---
const chartContainer = ref<HTMLElement | null>(null)
const { setOption, chart } = useChart(chartContainer)

// --- Computed ---
const filteredNodes = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  const nodes = store.sortedByRisk
  if (!q) return nodes
  return nodes.filter(n =>
    n.name.toLowerCase().includes(q) ||
    n.node_type.toLowerCase().includes(q) ||
    n.commodities?.some(c => c.toLowerCase().includes(q))
  )
})

// --- Helpers ---
function riskWidth(level: string): string {
  const map: Record<string, string> = {
    critical: '100%', high: '75%', elevated: '50%', normal: '25%',
  }
  return map[level] || '10%'
}

function riskNumeric(level: string): number {
  const map: Record<string, number> = {
    critical: 10, high: 7, elevated: 5, normal: 2,
  }
  return map[level] || 1
}

function getCommodityGroup(c: string): string {
  if (['crude_oil', 'lng', 'coal', 'natural_gas', 'diesel', 'gasoline'].includes(c)) return 'energy'
  if (['copper', 'iron_ore', 'aluminium', 'nickel', 'zinc', 'lithium'].includes(c)) return 'metals'
  if (['wheat', 'corn', 'soybeans', 'rice', 'sugar', 'coffee'].includes(c)) return 'agri'
  return 'other'
}

function typeIcon(type: string): string {
  const map: Record<string, string> = {
    port: 'pi-building',
    strait: 'pi-directions',
    canal: 'pi-directions',
    pipeline: 'pi-sitemap',
  }
  return map[type] || 'pi-map-marker'
}

function handleNodeClick(slug: string) {
  store.selectBottleneck(slug)
  mobileShowDetail.value = true
}

function closeDetail() {
  store.clearSelection()
  mobileShowDetail.value = false
}

function goToSimulation() {
  const slug = store.selectedBottleneck?.slug
  if (slug) {
    router.push({ path: localePath('/simulations'), query: { node: slug } })
  }
}

// --- Chart rendering ---
function renderChart() {
  const history = store.selectedBottleneck?.status_history
  if (!history?.length || !chart.value) return

  const dates = history.map(s => {
    const d = new Date(s.timestamp)
    return `${d.getMonth() + 1}/${d.getDate()}`
  })
  const congestionValues = history.map(s => s.congestion_index ?? 0)
  const vesselValues = history.map(s => s.vessel_count)

  // Compute a "normal" threshold as 40th percentile of congestion
  const sorted = [...congestionValues].sort((a, b) => a - b)
  const normalThreshold = sorted[Math.floor(sorted.length * 0.4)] || 0.5

  setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: '#475569' } },
    },
    grid: {
      left: 50,
      right: 20,
      top: 16,
      bottom: 30,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
    },
    yAxis: [
      {
        type: 'value',
        name: t('bottleneck.stats.congestion'),
        nameTextStyle: { fontSize: 11 },
        splitNumber: 4,
      },
      {
        type: 'value',
        name: t('bottleneck.stats.vessels'),
        nameTextStyle: { fontSize: 11 },
        splitNumber: 4,
      },
    ],
    series: [
      {
        name: t('bottleneck.stats.congestion'),
        type: 'line',
        data: congestionValues,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2.5, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(245, 158, 11, 0.3)' },
              { offset: 1, color: 'rgba(245, 158, 11, 0.02)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#22c55e', type: 'dashed', width: 1.5 },
          data: [{ yAxis: normalThreshold, label: { formatter: 'Normal', color: '#22c55e', fontSize: 10 } }],
        },
        yAxisIndex: 0,
      },
      {
        name: t('bottleneck.stats.vessels'),
        type: 'line',
        data: vesselValues,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 1.5, color: '#3b82f6', type: 'dashed' },
        itemStyle: { color: '#3b82f6' },
        yAxisIndex: 1,
      },
    ],
  })
}

// --- Watch for detail changes to update chart ---
watch(
  () => store.selectedBottleneck?.slug,
  async () => {
    if (store.selectedBottleneck?.status_history?.length) {
      await nextTick()
      // Re-init chart if container changed
      if (chartContainer.value && !chart.value) {
        // composable handles init on mount, but for dynamic show we need manual init
        const echarts = await import('echarts/core')
        chart.value = echarts.init(chartContainer.value, 'supplyshock-dark')
      }
      renderChart()
    }
  },
  { flush: 'post' }
)

watch(
  () => store.selectedBottleneck?.status_history,
  () => {
    if (store.selectedBottleneck?.status_history?.length) {
      nextTick(() => renderChart())
    }
  },
  { deep: true }
)

// --- Lifecycle ---
let refreshInterval: ReturnType<typeof setInterval> | null = null
let refreshLabelInterval: ReturnType<typeof setInterval> | null = null

async function loadBottlenecks() {
  listLoading.value = true
  listError.value = false
  try {
    await store.fetchBottlenecks()
    lastRefreshTime.value = new Date()
    updateRefreshLabel()
  } catch {
    listError.value = true
  } finally {
    listLoading.value = false
  }
}

function updateRefreshLabel() {
  if (!lastRefreshTime.value) {
    lastRefreshLabel.value = '—'
    return
  }
  const diff = Math.floor((Date.now() - lastRefreshTime.value.getTime()) / 1000)
  if (diff < 60) lastRefreshLabel.value = t('bottleneck.justNow')
  else if (diff < 3600) lastRefreshLabel.value = `${Math.floor(diff / 60)} min`
  else lastRefreshLabel.value = lastRefreshTime.value.toLocaleTimeString()
}

onMounted(() => {
  loadBottlenecks()
  // Auto-refresh every 5 minutes
  refreshInterval = setInterval(loadBottlenecks, 5 * 60 * 1000)
  refreshLabelInterval = setInterval(updateRefreshLabel, 30_000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (refreshLabelInterval) clearInterval(refreshLabelInterval)
})
</script>

<style scoped>
/* ========== Layout ========== */
.bottleneck-monitor {
  display: flex;
  height: calc(100vh - 64px);
  color: var(--ss-text-primary);
  overflow: hidden;
}

/* ========== Left Panel ========== */
.list-panel {
  width: 380px;
  min-width: 320px;
  max-width: 420px;
  background: var(--ss-bg-base);
  border-right: 1px solid var(--ss-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 1.25rem 1rem 0.75rem;
  border-bottom: 1px solid var(--ss-border);
  position: sticky;
  top: 0;
  background: var(--ss-bg-base);
  z-index: 10;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.panel-header h1 {
  font-size: 1.2rem;
  font-weight: 700;
  margin: 0;
}

.node-count {
  color: var(--ss-text-muted);
  font-size: 0.8rem;
}

/* Search */
.search-wrapper {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--ss-text-muted);
  font-size: 0.85rem;
}

.search-input {
  width: 100%;
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  padding: 0.55rem 2.25rem 0.55rem 2.25rem;
  color: var(--ss-text-primary);
  font-size: 0.85rem;
  outline: none;
  transition: border-color var(--ss-transition-fast);
}

.search-input:focus {
  border-color: var(--ss-accent);
}

.search-input::placeholder {
  color: var(--ss-text-muted);
}

.search-clear {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--ss-text-muted);
  cursor: pointer;
  padding: 0.25rem;
  font-size: 0.8rem;
}

/* List */
.bottleneck-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
}

.empty-list {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 1rem;
  color: var(--ss-text-muted);
  gap: 0.5rem;
}

.empty-list i {
  font-size: 2rem;
  opacity: 0.5;
}

/* Node Card */
.node-card {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 0.875rem 1rem;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.node-card:hover {
  border-color: var(--ss-text-muted);
  transform: translateX(2px);
}

.node-card.selected {
  border-color: var(--ss-accent);
  box-shadow: inset 3px 0 0 var(--ss-accent);
  background: rgba(20, 184, 166, 0.05);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.node-name {
  font-weight: 600;
  font-size: 0.9rem;
}

/* Risk badge */
.risk-badge {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 9999px;
  letter-spacing: 0.03em;
}

.risk-badge.risk-critical { background: rgba(239, 68, 68, 0.15); color: var(--ss-danger); }
.risk-badge.risk-high { background: rgba(249, 115, 22, 0.15); color: #f97316; }
.risk-badge.risk-elevated { background: rgba(234, 179, 8, 0.15); color: #eab308; }
.risk-badge.risk-normal { background: rgba(34, 197, 94, 0.15); color: var(--ss-success); }

/* Type badge */
.type-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: var(--ss-text-secondary);
  text-transform: capitalize;
}

.type-badge i {
  font-size: 0.7rem;
}

.type-badge.type-port { color: var(--ss-info); }
.type-badge.type-strait { color: var(--ss-warning); }
.type-badge.type-canal { color: var(--ss-accent); }
.type-badge.type-pipeline { color: #a78bfa; }

.node-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.vessel-count {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--ss-text-muted);
  font-size: 0.75rem;
}

.vessel-count i {
  font-size: 0.65rem;
}

/* Risk bar */
.risk-bar-container {
  height: 4px;
  background: var(--ss-bg-elevated);
  border-radius: 2px;
  margin-bottom: 0.6rem;
  position: relative;
}

.risk-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}

.risk-bar.risk-critical { background: linear-gradient(90deg, #ef4444, #dc2626); }
.risk-bar.risk-high { background: linear-gradient(90deg, #f97316, #ea580c); }
.risk-bar.risk-elevated { background: linear-gradient(90deg, #eab308, #ca8a04); }
.risk-bar.risk-normal { background: linear-gradient(90deg, #22c55e, #16a34a); }

.risk-bar-label {
  position: absolute;
  right: 0;
  top: -14px;
  font-size: 0.6rem;
  color: var(--ss-text-muted);
}

/* Commodity tags */
.commodity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.tag {
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: capitalize;
}

.tag-energy { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }
.tag-metals { background: rgba(59, 130, 246, 0.12); color: #93c5fd; }
.tag-agri { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.tag-other { background: var(--ss-bg-elevated); color: var(--ss-text-secondary); }
.tag-more { background: transparent; color: var(--ss-text-muted); font-style: italic; }

/* Refresh indicator */
.refresh-indicator {
  padding: 0.5rem 1rem;
  border-top: 1px solid var(--ss-border);
  text-align: center;
}

.refresh-text {
  font-size: 0.7rem;
  color: var(--ss-text-muted);
}

/* ========== Right Panel: Detail ========== */
.detail-panel {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
  position: relative;
  min-width: 0;
}

.close-detail {
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  color: var(--ss-text-muted);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.close-detail:hover {
  color: var(--ss-text-primary);
  border-color: var(--ss-text-muted);
}

/* Mobile back button */
.mobile-back {
  display: none;
}

/* Detail header */
.detail-header {
  margin-bottom: 1.25rem;
}

.detail-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Description */
.detail-description {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1rem 1.25rem;
  color: var(--ss-text-secondary);
  font-size: 0.875rem;
  line-height: 1.65;
  margin-bottom: 1.25rem;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  padding: 1rem;
  text-align: center;
  transition: border-color var(--ss-transition-fast);
}

.stat-card:hover {
  border-color: var(--ss-accent-dim);
}

.stat-icon {
  margin-bottom: 0.4rem;
  color: var(--ss-text-muted);
  font-size: 1.1rem;
}

.stat-icon.risk-icon.risk-critical { color: var(--ss-danger); }
.stat-icon.risk-icon.risk-high { color: #f97316; }
.stat-icon.risk-icon.risk-elevated { color: #eab308; }
.stat-icon.risk-icon.risk-normal { color: var(--ss-success); }

.stat-label {
  color: var(--ss-text-muted);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.3rem;
}

.stat-value {
  font-size: 1.2rem;
  font-weight: 700;
}

.stat-unit {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--ss-text-muted);
}

.text-critical { color: var(--ss-danger); }
.text-high { color: #f97316; }
.text-elevated { color: #eab308; }
.text-normal { color: var(--ss-success); }

/* Chart Section */
.chart-section {
  margin-bottom: 1.5rem;
}

.chart-section h3 {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
}

.chart-container {
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius-lg);
  height: 260px;
  width: 100%;
}

/* Commodities Section */
.commodities-section {
  margin-bottom: 1.5rem;
}

.commodities-section h3 {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
}

.commodity-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.commodity-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: capitalize;
}

.chip-energy { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }
.chip-metals { background: rgba(59, 130, 246, 0.12); color: #93c5fd; }
.chip-agri { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.chip-other { background: var(--ss-bg-elevated); color: var(--ss-text-secondary); }

/* Simulation Button */
.sim-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--ss-accent);
  color: #fff;
  border: none;
  padding: 0.75rem 1.75rem;
  border-radius: var(--ss-radius);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
  width: auto;
}

.sim-btn:hover {
  background: var(--ss-accent-light);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(20, 184, 166, 0.3);
}

/* Empty detail */
.empty-detail {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--ss-text-muted);
  text-align: center;
  gap: 0.75rem;
}

.empty-illustration {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--ss-bg-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.5rem;
}

.empty-illustration i {
  font-size: 2rem;
  color: var(--ss-text-muted);
  opacity: 0.5;
}

.empty-detail h3 {
  font-size: 1.1rem;
  color: var(--ss-text-secondary);
  margin: 0;
}

.empty-detail p {
  font-size: 0.85rem;
  max-width: 300px;
  line-height: 1.5;
}

/* ========== Skeleton ========== */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-line {
  background: linear-gradient(
    90deg,
    var(--ss-bg-elevated) 25%,
    rgba(100, 116, 139, 0.15) 50%,
    var(--ss-bg-elevated) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite ease-in-out;
  border-radius: 4px;
}

.skeleton-card {
  cursor: default !important;
}
.skeleton-card:hover {
  transform: none !important;
  border-color: var(--ss-border-light) !important;
}

.skeleton-title { height: 16px; width: 70%; margin-bottom: 0.6rem; }
.skeleton-meta { height: 12px; width: 45%; margin-bottom: 0.5rem; }
.skeleton-bar { height: 4px; width: 100%; margin-bottom: 0.6rem; }
.skeleton-tags { display: flex; gap: 0.3rem; }
.skeleton-tag { height: 18px; width: 50px; border-radius: 4px; }

.skeleton-detail-title { height: 24px; width: 50%; margin-bottom: 0.75rem; }
.skeleton-detail-sub { height: 14px; width: 30%; margin-bottom: 1.5rem; }
.skeleton-stat-label { height: 10px; width: 60%; margin: 0 auto 0.4rem; }
.skeleton-stat-value { height: 20px; width: 40%; margin: 0 auto; }
.skeleton-chart { height: 200px; width: 100%; margin-top: 1rem; border-radius: var(--ss-radius-lg); }

/* Detail loading */
.detail-loading {
  padding: 1rem 0;
}

/* ========== Error ========== */
.list-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  gap: 0.75rem;
  color: var(--ss-text-muted);
}

.error-icon {
  font-size: 2.5rem;
  color: var(--ss-warning);
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--ss-bg-surface);
  border: 1px solid var(--ss-border-light);
  border-radius: var(--ss-radius);
  color: var(--ss-text-primary);
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--ss-transition-fast);
}

.retry-btn:hover {
  border-color: var(--ss-accent);
  color: var(--ss-accent);
}

/* ========== Responsive: Tablet ========== */
@media (max-width: 1024px) {
  .bottleneck-monitor {
    flex-direction: column;
    height: auto;
    min-height: calc(100vh - 64px);
  }

  .list-panel {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--ss-border);
    max-height: 45vh;
  }

  .detail-panel {
    flex: 1;
    min-height: 55vh;
    padding: 1.25rem;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .desktop-only {
    display: flex;
  }
}

/* ========== Responsive: Mobile ========== */
@media (max-width: 640px) {
  .bottleneck-monitor {
    flex-direction: column;
    position: relative;
  }

  .list-panel {
    max-height: none;
    height: 100%;
    flex: 1;
    border-bottom: none;
  }

  .list-panel.mobile-hidden {
    display: none;
  }

  .detail-panel {
    display: none;
    padding: 1rem;
  }

  .detail-panel.mobile-visible {
    display: flex;
    flex-direction: column;
    position: fixed;
    inset: 0;
    top: 64px;
    z-index: 100;
    background: var(--ss-bg-base);
    overflow-y: auto;
  }

  .mobile-back {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: none;
    border: none;
    color: var(--ss-accent);
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0.5rem 0;
    margin-bottom: 0.75rem;
  }

  .desktop-only {
    display: none !important;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .detail-header h2 {
    font-size: 1.25rem;
  }

  .chart-container {
    height: 200px;
  }

  .sim-btn {
    width: 100%;
    justify-content: center;
  }
}

/* ========== Animation ========== */
.fade-in {
  animation: fadeIn var(--ss-transition) ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
