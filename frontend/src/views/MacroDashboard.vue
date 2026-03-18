<template>
  <div class="view-container fade-in">
    <header class="view-header">
      <h1>{{ t('macro.title') }}</h1>
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
const activeTab = ref('pmi')

const PMIChart = defineAsyncComponent(() => import('@/components/macro/PMIChart.vue'))
const TradeFlowsChart = defineAsyncComponent(() => import('@/components/macro/TradeFlowsChart.vue'))
const FXPanel = defineAsyncComponent(() => import('@/components/analytics/FXPanel.vue'))
const RatesChart = defineAsyncComponent(() => import('@/components/macro/RatesChart.vue'))
const UncertaintyChart = defineAsyncComponent(() => import('@/components/macro/UncertaintyChart.vue'))

const tabs = [
  { key: 'pmi', icon: 'pi-chart-line', label: () => t('macro.tabs.pmi') },
  { key: 'tradeFlows', icon: 'pi-arrows-h', label: () => t('macro.tabs.tradeFlows') },
  { key: 'fx', icon: 'pi-dollar', label: () => t('macro.tabs.fx') },
  { key: 'rates', icon: 'pi-percentage', label: () => t('macro.tabs.rates') },
  { key: 'uncertainty', icon: 'pi-exclamation-triangle', label: () => t('macro.tabs.uncertainty') }
]

const componentMap: Record<string, any> = {
  pmi: PMIChart,
  tradeFlows: TradeFlowsChart,
  fx: FXPanel,
  rates: RatesChart,
  uncertainty: UncertaintyChart
}

const activeComponent = computed(() => componentMap[activeTab.value] || PMIChart)
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
