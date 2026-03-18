<template>
  <div class="base-bar-chart">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, type PropType } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

/* ── Types ── */
export interface BarSeriesData {
  name: string
  values: number[]
  color?: string
}

/* ── Props ── */
const props = defineProps({
  /** Array of series, each with a name and values array */
  data: {
    type: Array as PropType<BarSeriesData[]>,
    required: true,
  },
  /** Category labels for the x-axis */
  categories: {
    type: Array as PropType<string[]>,
    required: true,
  },
  /** Enable stacked bars */
  stacked: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '',
  },
})

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const PALETTE = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#ec4899', '#84cc16']

function buildOptions(): echarts.EChartsOption {
  const series = props.data.map((s, i) => ({
    name: s.name,
    type: 'bar' as const,
    data: s.values,
    stack: props.stacked ? 'total' : undefined,
    itemStyle: { color: s.color || PALETTE[i % PALETTE.length] },
    barMaxWidth: 40,
  }))

  return {
    backgroundColor: 'transparent',
    grid: { top: 40, right: 20, bottom: 40, left: 60, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#f1f5f9', fontSize: 12 },
    },
    legend: {
      show: props.data.length > 1,
      top: 8,
      textStyle: { color: '#94a3b8', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: props.categories,
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
    },
    series,
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  chart.setOption(buildOptions(), true)
}

function handleResize() {
  chart?.resize()
}

watch(
  () => [props.data, props.categories, props.stacked],
  () => nextTick(renderChart),
  { deep: true }
)

onMounted(() => {
  nextTick(renderChart)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.base-bar-chart {
  width: 100%;
}
.chart-title {
  font-size: var(--ss-text-sm, 0.875rem);
  font-weight: 600;
  color: var(--ss-text-primary, #f8fafc);
  margin-bottom: var(--ss-space-sm, 8px);
}
.chart-container {
  width: 100%;
  height: 400px;
}
</style>
