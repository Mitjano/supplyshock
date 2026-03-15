<template>
  <div class="right-panel" :class="{ collapsed: isCollapsed }">
    <button class="toggle-btn" @click="isCollapsed = !isCollapsed">
      {{ isCollapsed ? '◀' : '▶' }}
    </button>

    <div v-if="!isCollapsed" class="panel-content">
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Chokepoints tab -->
      <div v-if="activeTab === 'chokepoints'" class="tab-content">
        <div v-for="node in chokepoints" :key="node.slug" class="item-card">
          <div class="item-header">
            <span class="item-name">{{ node.name }}</span>
            <span class="risk-badge" :class="riskClass(node.risk)">{{ node.risk }}</span>
          </div>
          <div class="item-meta">
            {{ node.type }} · {{ node.country }}
            <span v-if="node.vesselCount" class="vessel-count">{{ node.vesselCount }} vessels</span>
          </div>
        </div>
      </div>

      <!-- Alerts tab -->
      <div v-if="activeTab === 'alerts'" class="tab-content">
        <div v-for="alert in alerts" :key="alert.id" class="item-card">
          <div class="item-header">
            <span class="item-name">{{ alert.title }}</span>
            <span class="severity-badge" :class="alert.severity">{{ alert.severity }}</span>
          </div>
          <div class="item-meta">{{ alert.time }}</div>
        </div>
        <div v-if="!alerts.length" class="empty-state">No recent alerts</div>
      </div>

      <!-- Flows tab -->
      <div v-if="activeTab === 'flows'" class="tab-content">
        <table class="flows-table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Commodity</th>
              <th>Volume</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(flow, i) in topFlows" :key="i">
              <td>{{ flow.origin }} → {{ flow.destination }}</td>
              <td>
                <span class="commodity-dot" :style="{ background: commodityColor(flow.commodity) }"></span>
                {{ formatCommodity(flow.commodity) }}
              </td>
              <td>{{ formatVolume(flow.volume_mt) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMapStore } from '../../stores/useMapStore'

const mapStore = useMapStore()
const isCollapsed = ref(false)
const activeTab = ref('chokepoints')

const tabs = [
  { id: 'chokepoints', label: 'Chokepoints' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'flows', label: 'Flows' },
]

// Placeholder chokepoints — will be replaced with API data
const chokepoints = ref([
  { slug: 'strait_hormuz', name: 'Strait of Hormuz', type: 'strait', country: 'OM', risk: 9, vesselCount: 42 },
  { slug: 'strait_malacca', name: 'Strait of Malacca', type: 'strait', country: 'SG', risk: 7, vesselCount: 85 },
  { slug: 'suez_canal', name: 'Suez Canal', type: 'strait', country: 'EG', risk: 8, vesselCount: 31 },
  { slug: 'panama_canal', name: 'Panama Canal', type: 'strait', country: 'PA', risk: 6, vesselCount: 18 },
  { slug: 'bab_el_mandeb', name: 'Bab el-Mandeb', type: 'strait', country: 'DJ', risk: 8, vesselCount: 22 },
  { slug: 'turkish_straits', name: 'Turkish Straits', type: 'strait', country: 'TR', risk: 6, vesselCount: 15 },
  { slug: 'cape_good_hope', name: 'Cape of Good Hope', type: 'strait', country: 'ZA', risk: 4, vesselCount: 60 },
])

// Placeholder alerts
const alerts = ref<Array<{ id: string; title: string; severity: string; time: string }>>([])

const topFlows = computed(() => {
  return mapStore.tradeFlows.slice(0, 6).map(f => ({
    origin: f.properties.origin,
    destination: f.properties.destination,
    commodity: f.properties.commodity,
    volume_mt: f.properties.volume_mt,
  }))
})

const COMMODITY_COLORS: Record<string, string> = {
  crude_oil: '#ef4444',
  coal: '#374151',
  iron_ore: '#b45309',
  copper: '#d97706',
  lng: '#10b981',
}

function commodityColor(c: string) { return COMMODITY_COLORS[c] || '#6b7280' }
function formatCommodity(c: string) { return c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) }
function formatVolume(v: number | null) { return v ? `${(v / 1000).toFixed(0)}k MT` : '—' }
function riskClass(risk: number) { return risk >= 8 ? 'high' : risk >= 5 ? 'medium' : 'low' }
</script>

<style scoped>
.right-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 320px;
  height: 100%;
  background: rgba(15, 23, 42, 0.95);
  border-left: 1px solid #1e293b;
  z-index: 20;
  transition: width 0.2s;
  display: flex;
  flex-direction: column;
}

.right-panel.collapsed {
  width: 0;
  overflow: hidden;
}

.toggle-btn {
  position: absolute;
  left: -28px;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid #334155;
  border-right: none;
  border-radius: 6px 0 0 6px;
  color: #94a3b8;
  padding: 0.5rem 0.25rem;
  cursor: pointer;
  font-size: 0.75rem;
}

.panel-content {
  overflow-y: auto;
  flex: 1;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #1e293b;
}

.tab-btn {
  flex: 1;
  padding: 0.75rem 0.5rem;
  background: none;
  border: none;
  color: #64748b;
  font-size: 0.8rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab-content {
  padding: 0.75rem;
}

.item-card {
  padding: 0.75rem;
  border-bottom: 1px solid #1e293b;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.item-name {
  color: #e2e8f0;
  font-size: 0.9rem;
  font-weight: 500;
}

.item-meta {
  color: #64748b;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.vessel-count {
  color: #94a3b8;
  margin-left: 0.5rem;
}

.risk-badge, .severity-badge {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
}

.risk-badge.high, .severity-badge.critical { background: #991b1b; color: #fca5a5; }
.risk-badge.medium, .severity-badge.warning { background: #92400e; color: #fcd34d; }
.risk-badge.low, .severity-badge.info { background: #1e3a5f; color: #93c5fd; }

.empty-state {
  text-align: center;
  color: #475569;
  padding: 2rem 0;
  font-size: 0.9rem;
}

.flows-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.flows-table th {
  color: #64748b;
  text-align: left;
  padding: 0.5rem 0.25rem;
  font-weight: 500;
  border-bottom: 1px solid #1e293b;
}

.flows-table td {
  color: #cbd5e1;
  padding: 0.5rem 0.25rem;
  border-bottom: 1px solid #0f172a;
}

.commodity-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
}

@media (max-width: 768px) {
  .right-panel {
    width: 100%;
    height: 40%;
    top: auto;
    bottom: 0;
    border-left: none;
    border-top: 1px solid #1e293b;
  }

  .toggle-btn {
    left: 50%;
    top: -28px;
    transform: translateX(-50%);
    border-radius: 6px 6px 0 0;
    border: 1px solid #334155;
    border-bottom: none;
  }
}
</style>
