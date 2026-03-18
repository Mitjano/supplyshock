<template>
  <div class="ss-stat-card">
    <div class="stat-header">
      <span v-if="icon" class="stat-icon"><i :class="icon" /></span>
      <span class="stat-label">{{ label }}</span>
    </div>
    <div class="stat-value">{{ value }}</div>
    <div v-if="change != null || changePercent != null" class="stat-change" :class="changeClass">
      <span v-if="changePercent != null" class="change-percent">
        {{ changePercent >= 0 ? '+' : '' }}{{ changePercent.toFixed(2) }}%
      </span>
      <span v-if="change != null" class="change-abs">
        ({{ change >= 0 ? '+' : '' }}{{ change }})
      </span>
    </div>
    <div v-if="sparklineData && sparklineData.length" ref="sparkRef" class="stat-sparkline" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch, type PropType } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, CanvasRenderer])

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  change: { type: Number, default: undefined },
  changePercent: { type: Number, default: undefined },
  icon: { type: String, default: '' },
  sparklineData: {
    type: Array as PropType<number[]>,
    default: () => [],
  },
})

const sparkRef = ref<HTMLElement | null>(null)
let sparkChart: echarts.ECharts | null = null

const changeClass = computed(() => {
  const val = props.changePercent ?? props.change ?? 0
  if (val > 0) return 'positive'
  if (val < 0) return 'negative'
  return 'neutral'
})

function renderSparkline() {
  if (!sparkRef.value || !props.sparklineData?.length) return
  if (!sparkChart) {
    sparkChart = echarts.init(sparkRef.value)
  }
  const color = changeClass.value === 'positive' ? '#22c55e' : changeClass.value === 'negative' ? '#ef4444' : '#94a3b8'
  sparkChart.setOption({
    grid: { top: 2, right: 0, bottom: 2, left: 0 },
    xAxis: { type: 'category', show: false },
    yAxis: { type: 'value', show: false },
    series: [
      {
        type: 'line',
        data: props.sparklineData,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.5, color },
        areaStyle: { color: `${color}22` },
      },
    ],
  })
}

watch(() => props.sparklineData, () => nextTick(renderSparkline), { deep: true })

onMounted(() => nextTick(renderSparkline))
onUnmounted(() => {
  sparkChart?.dispose()
  sparkChart = null
})
</script>

<style scoped>
.ss-stat-card {
  background: var(--ss-bg-secondary, #1e293b);
  border: 1px solid var(--ss-border-light, #334155);
  border-radius: var(--ss-radius-lg, 8px);
  padding: var(--ss-space-lg, 16px);
  display: flex;
  flex-direction: column;
  gap: var(--ss-space-xs, 4px);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: var(--ss-space-sm, 8px);
}

.stat-icon {
  color: var(--ss-accent, #3b82f6);
  font-size: var(--ss-text-md, 1rem);
}

.stat-label {
  color: var(--ss-text-muted, #94a3b8);
  font-size: var(--ss-text-xs, 0.75rem);
  font-weight: var(--ss-font-medium, 500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  color: var(--ss-text-primary, #f8fafc);
  font-size: var(--ss-text-2xl, 1.5rem);
  font-weight: var(--ss-font-bold, 700);
  line-height: var(--ss-leading-tight, 1.25);
}

.stat-change {
  font-size: var(--ss-text-sm, 0.875rem);
  font-weight: var(--ss-font-medium, 500);
  display: flex;
  align-items: center;
  gap: var(--ss-space-xs, 4px);
}

.stat-change.positive { color: var(--ss-success, #22c55e); }
.stat-change.negative { color: var(--ss-danger, #ef4444); }
.stat-change.neutral  { color: var(--ss-text-muted, #94a3b8); }

.stat-sparkline {
  width: 100%;
  height: 32px;
  margin-top: var(--ss-space-xs, 4px);
}
</style>
