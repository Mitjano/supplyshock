<template>
  <div class="view-container fade-in">
    <header class="view-header">
      <h1>{{ t('analytics.dashboard.title') }}</h1>
    </header>

    <!-- Tab bar -->
    <div class="analytics-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <i :class="['pi', tab.icon]" />
        {{ tab.label() }}
      </button>
    </div>

    <!-- Lazy-loaded tab content -->
    <div class="ss-card tab-content">
      <Suspense>
        <template #default>
          <component :is="activeComponent" />
        </template>
        <template #fallback>
          <div class="loading-state">
            <i class="pi pi-spin pi-spinner" />
            <p>{{ t('common.loading') }}</p>
          </div>
        </template>
      </Suspense>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const activeTab = ref('cot')

const COTChart = defineAsyncComponent(() => import('@/components/analytics/COTChart.vue'))
const InventoryChart = defineAsyncComponent(() => import('@/components/analytics/InventoryChart.vue'))
const CrackSpreadChart = defineAsyncComponent(() => import('@/components/analytics/CrackSpreadChart.vue'))
const CorrelationMatrix = defineAsyncComponent(() => import('@/components/analytics/CorrelationMatrix.vue'))
const SeasonalChart = defineAsyncComponent(() => import('@/components/analytics/SeasonalChart.vue'))
const ForwardCurveChart = defineAsyncComponent(() => import('@/components/analytics/ForwardCurveChart.vue'))
const BalanceChart = defineAsyncComponent(() => import('@/components/analytics/BalanceChart.vue'))
const PortAnalyticsPanel = defineAsyncComponent(() => import('@/components/analytics/PortAnalyticsPanel.vue'))
const RigCountChart = defineAsyncComponent(() => import('@/components/analytics/RigCountChart.vue'))
const NatGasStorageChart = defineAsyncComponent(() => import('@/components/analytics/NatGasStorageChart.vue'))
const SPRTracker = defineAsyncComponent(() => import('@/components/analytics/SPRTracker.vue'))
const CropProgressChart = defineAsyncComponent(() => import('@/components/analytics/CropProgressChart.vue'))
const CarbonPriceChart = defineAsyncComponent(() => import('@/components/analytics/CarbonPriceChart.vue'))
const BunkerPriceChart = defineAsyncComponent(() => import('@/components/analytics/BunkerPriceChart.vue'))

const tabs = [
  { key: 'cot', icon: 'pi-chart-bar', label: () => t('analytics.dashboard.tabs.cot') },
  { key: 'inventories', icon: 'pi-database', label: () => t('analytics.dashboard.tabs.inventories') },
  { key: 'cracks', icon: 'pi-sliders-h', label: () => t('analytics.dashboard.tabs.cracks') },
  { key: 'correlations', icon: 'pi-th-large', label: () => t('analytics.dashboard.tabs.correlations') },
  { key: 'seasonal', icon: 'pi-calendar', label: () => t('analytics.dashboard.tabs.seasonal') },
  { key: 'forwardCurves', icon: 'pi-chart-line', label: () => t('analytics.dashboard.tabs.forwardCurves') },
  { key: 'balance', icon: 'pi-chart-pie', label: () => t('analytics.dashboard.tabs.balance') },
  { key: 'ports', icon: 'pi-map-marker', label: () => t('analytics.dashboard.tabs.ports') },
  { key: 'rigCount', icon: 'pi-wrench', label: () => t('analytics.dashboard.tabs.rigCount') },
  { key: 'natGas', icon: 'pi-bolt', label: () => t('analytics.dashboard.tabs.natGas') },
  { key: 'spr', icon: 'pi-warehouse', label: () => t('analytics.dashboard.tabs.spr') },
  { key: 'crops', icon: 'pi-sun', label: () => t('analytics.dashboard.tabs.crops') },
  { key: 'carbon', icon: 'pi-cloud', label: () => t('analytics.dashboard.tabs.carbon') },
  { key: 'bunker', icon: 'pi-truck', label: () => t('analytics.dashboard.tabs.bunker') }
]

const componentMap: Record<string, any> = {
  cot: COTChart,
  inventories: InventoryChart,
  cracks: CrackSpreadChart,
  correlations: CorrelationMatrix,
  seasonal: SeasonalChart,
  forwardCurves: ForwardCurveChart,
  balance: BalanceChart,
  ports: PortAnalyticsPanel,
  rigCount: RigCountChart,
  natGas: NatGasStorageChart,
  spr: SPRTracker,
  crops: CropProgressChart,
  carbon: CarbonPriceChart,
  bunker: BunkerPriceChart
}

const activeComponent = computed(() => componentMap[activeTab.value] || COTChart)
</script>

<style scoped>
.view-header { margin-bottom: 1.5rem; }
.view-header h1 { font-size: 1.5rem; font-weight: 700; }
.analytics-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.tab-btn {
  padding: 0.5rem 1rem; border-radius: 8px; border: 1px solid var(--border-color, #2a2a3e);
  background: transparent; color: var(--text-secondary, #94a3b8); cursor: pointer;
  font-size: 0.85rem; transition: all 0.2s; display: flex; align-items: center; gap: 0.4rem;
}
.tab-btn:hover { background: var(--bg-hover, rgba(255,255,255,0.05)); }
.tab-btn.active { background: var(--accent, #3b82f6); color: white; border-color: transparent; }
.tab-content { padding: 1.5rem; min-height: 450px; }
.loading-state { text-align: center; padding: 3rem; color: var(--ss-text-secondary); }
.loading-state i { font-size: 2rem; display: block; margin-bottom: 1rem; }
</style>
