<template>
  <div class="bottleneck-monitor">
    <div class="list-panel">
      <header class="panel-header">
        <h1>Bottleneck Monitor</h1>
        <span class="node-count">{{ store.bottlenecks.length }} nodes</span>
      </header>

      <div class="bottleneck-list">
        <div
          v-for="node in store.sortedByRisk"
          :key="node.slug"
          :class="['node-card', { selected: store.selectedBottleneck?.slug === node.slug }]"
          @click="store.selectBottleneck(node.slug)"
        >
          <div class="node-header">
            <span class="node-name">{{ node.name }}</span>
            <span :class="['risk-badge', `risk-${node.risk_level}`]">
              {{ node.risk_level }}
            </span>
          </div>
          <div class="node-meta">
            <span class="node-type">{{ node.node_type }}</span>
            <span v-if="node.vessel_count" class="vessel-count">
              {{ node.vessel_count }} vessels
            </span>
          </div>
          <div class="risk-bar-container">
            <div
              class="risk-bar"
              :class="`risk-${node.risk_level}`"
              :style="{ width: riskWidth(node.risk_level) }"
            />
          </div>
          <div class="commodity-tags">
            <span
              v-for="c in node.commodities"
              :key="c"
              :class="['tag', `tag-${getCommodityGroup(c)}`]"
            >
              {{ c.replace(/_/g, ' ') }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="detail-panel" v-if="store.selectedBottleneck">
      <button class="close-detail" @click="store.clearSelection()">&times;</button>
      <h2>{{ store.selectedBottleneck.name }}</h2>
      <div class="detail-type">{{ store.selectedBottleneck.node_type }}</div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Vessels</div>
          <div class="stat-value">{{ store.selectedBottleneck.vessel_count ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg Speed</div>
          <div class="stat-value">
            {{ store.selectedBottleneck.avg_speed?.toFixed(1) ?? '—' }} kn
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Congestion</div>
          <div class="stat-value">
            {{ store.selectedBottleneck.congestion_index?.toFixed(2) ?? '—' }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Risk</div>
          <div
            :class="['stat-value', `text-${store.selectedBottleneck.risk_level}`]"
          >
            {{ store.selectedBottleneck.risk_level }}
          </div>
        </div>
      </div>

      <div v-if="store.selectedBottleneck.throughput_description" class="throughput">
        {{ store.selectedBottleneck.throughput_description }}
      </div>

      <div class="history-section" v-if="store.selectedBottleneck.status_history.length">
        <h3>7-Day History</h3>
        <div class="history-chart">
          <svg viewBox="0 0 600 150" preserveAspectRatio="none" class="history-svg">
            <polyline
              :points="historyChartPoints"
              fill="none"
              stroke="#f59e0b"
              stroke-width="2"
            />
          </svg>
          <div class="history-labels">
            <span>{{ historyMin }} vessels</span>
            <span>{{ historyMax }} vessels</span>
          </div>
        </div>
      </div>

      <button class="sim-btn" @click="goToSimulation">
        Run Simulation
      </button>
    </div>

    <div class="detail-panel empty-detail" v-else>
      <p>Select a bottleneck node to view details</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useBottleneckStore } from '../stores/useBottleneckStore'

const store = useBottleneckStore()
const router = useRouter()

function riskWidth(level: string): string {
  const map: Record<string, string> = {
    critical: '100%', high: '75%', elevated: '50%', normal: '25%',
  }
  return map[level] || '10%'
}

function getCommodityGroup(c: string): string {
  if (['crude_oil', 'lng', 'coal'].includes(c)) return 'energy'
  if (['copper', 'iron_ore', 'aluminium', 'nickel'].includes(c)) return 'metals'
  return 'other'
}

const historyMin = computed(() => {
  const h = store.selectedBottleneck?.status_history || []
  if (!h.length) return 0
  return Math.min(...h.map(s => s.vessel_count))
})

const historyMax = computed(() => {
  const h = store.selectedBottleneck?.status_history || []
  if (!h.length) return 0
  return Math.max(...h.map(s => s.vessel_count))
})

const historyChartPoints = computed(() => {
  const h = store.selectedBottleneck?.status_history || []
  if (!h.length) return ''
  const range = historyMax.value - historyMin.value || 1
  return h
    .map((s, i) => {
      const x = (i / (h.length - 1)) * 600
      const y = 150 - ((s.vessel_count - historyMin.value) / range) * 130 - 10
      return `${x},${y}`
    })
    .join(' ')
})

function goToSimulation() {
  const slug = store.selectedBottleneck?.slug
  if (slug) {
    router.push({ path: '/simulation', query: { node: slug } })
  }
}

onMounted(() => {
  store.fetchBottlenecks()
})
</script>

<style scoped>
.bottleneck-monitor {
  display: grid;
  grid-template-columns: 400px 1fr;
  height: 100vh;
  color: #f1f5f9;
}

.list-panel {
  background: #0f172a;
  border-right: 1px solid #1e293b;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #1e293b;
  position: sticky;
  top: 0;
  background: #0f172a;
  z-index: 10;
}

.panel-header h1 {
  font-size: 1.25rem;
  margin: 0;
}

.node-count {
  color: #64748b;
  font-size: 0.85rem;
}

.bottleneck-list {
  padding: 0.75rem;
}

.node-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.node-card:hover {
  border-color: #475569;
}

.node-card.selected {
  border-color: #f59e0b;
  box-shadow: 0 0 0 1px #f59e0b;
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.node-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.risk-badge {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 4px;
}

.risk-badge.risk-critical { background: #dc2626; color: #fff; }
.risk-badge.risk-high { background: #ea580c; color: #fff; }
.risk-badge.risk-elevated { background: #ca8a04; color: #fff; }
.risk-badge.risk-normal { background: #334155; color: #94a3b8; }

.node-meta {
  display: flex;
  gap: 1rem;
  color: #64748b;
  font-size: 0.8rem;
  margin-bottom: 0.5rem;
}

.risk-bar-container {
  height: 4px;
  background: #334155;
  border-radius: 2px;
  margin-bottom: 0.75rem;
}

.risk-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.risk-bar.risk-critical { background: #dc2626; }
.risk-bar.risk-high { background: #ea580c; }
.risk-bar.risk-elevated { background: #ca8a04; }
.risk-bar.risk-normal { background: #475569; }

.commodity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.tag {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: #334155;
  color: #94a3b8;
}

.tag-energy { background: #7f1d1d; color: #fca5a5; }
.tag-metals { background: #1e3a5f; color: #93c5fd; }

.detail-panel {
  padding: 2rem;
  overflow-y: auto;
  position: relative;
}

.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
}

.close-detail {
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  background: none;
  border: none;
  color: #64748b;
  font-size: 1.5rem;
  cursor: pointer;
}

.detail-panel h2 {
  font-size: 1.5rem;
  margin: 0 0 0.25rem;
}

.detail-type {
  color: #64748b;
  font-size: 0.9rem;
  text-transform: capitalize;
  margin-bottom: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: #1e293b;
  border-radius: 10px;
  padding: 1rem;
  text-align: center;
}

.stat-label {
  color: #64748b;
  font-size: 0.75rem;
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
}

.text-critical { color: #ef4444; }
.text-high { color: #f97316; }
.text-elevated { color: #eab308; }
.text-normal { color: #10b981; }

.throughput {
  background: #1e293b;
  border-radius: 10px;
  padding: 1rem;
  color: #94a3b8;
  font-size: 0.9rem;
  line-height: 1.6;
  margin-bottom: 1.5rem;
}

.history-section h3 {
  font-size: 1rem;
  margin: 0 0 0.75rem;
}

.history-chart {
  background: #1e293b;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.history-svg {
  width: 100%;
  height: 150px;
}

.history-labels {
  display: flex;
  justify-content: space-between;
  color: #64748b;
  font-size: 0.75rem;
  margin-top: 0.5rem;
}

.sim-btn {
  background: #3b82f6;
  color: #fff;
  border: none;
  padding: 0.75rem 2rem;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  width: 100%;
}

.sim-btn:hover {
  background: #2563eb;
}
</style>
