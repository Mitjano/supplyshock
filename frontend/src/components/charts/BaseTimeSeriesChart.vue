<template>
  <div class="base-time-series-chart">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, type PropType } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
  CanvasRenderer,
])

/* ── Types ── */
export interface TimeSeriesPoint {
  time: number | string
  value: number
}

export interface OverlayBand {
  type: 'band'
  label?: string
  upper: TimeSeriesPoint[]
  lower: TimeSeriesPoint[]
  color?: string
}

export interface OverlayLine {
  type: 'line'
  label?: string
  value: number
  color?: string
  dash?: boolean
}

export type Overlay = OverlayBand | OverlayLine

/* ── Props ── */
const props = defineProps({
  data: {
    type: Array as PropType<TimeSeriesPoint[]>,
    required: true,
  },
  overlays: {
    type: Array as PropType<Overlay[]>,
    default: () => [],
  },
  title: {
    type: String,
    default: '',
  },
  yAxisLabel: {
    type: String,
    default: '',
  },
  timeRange: {
    type: String as PropType<string>,
    default: 'ALL',
  },
})

/* ── Chart instance ── */
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function buildOptions(): echarts.EChartsOption {
  const times = props.data.map((d) => d.time)
  const values = props.data.map((d) => d.value)

  const series: any[] = [
    {
      name: props.title || 'Value',
      type: 'line',
      data: values,
      showSymbol: false,
      smooth: false,
      lineStyle: { width: 2, color: '#3b82f6' },
      areaStyle: { color: 'rgba(59, 130, 246, 0.08)' },
      markLine: { data: [] as any[], silent: true },
    },
  ]

  // Overlay reference lines (dashed horizontal)
  for (const ol of props.overlays) {
    if (ol.type === 'line') {
      series[0].markLine.data.push({
        yAxis: ol.value,
        name: ol.label || '',
        lineStyle: {
          color: ol.color || '#94a3b8',
          type: ol.dash !== false ? 'dashed' : 'solid',
          width: 1,
        },
        label: {
          formatter: ol.label || '',
          color: '#cbd5e1',
          fontSize: 11,
        },
      })
    }
  }

  // Overlay bands (area between upper and lower)
  for (const ol of props.overlays) {
    if (ol.type === 'band') {
      series.push({
        name: ol.label || 'Upper',
        type: 'line',
        data: ol.upper.map((d) => d.value),
        showSymbol: false,
        lineStyle: { width: 0 },
        areaStyle: { color: ol.color || 'rgba(59, 130, 246, 0.12)' },
        stack: ol.label || 'band',
        silent: true,
      })
      series.push({
        name: (ol.label || 'Lower') + ' (lower)',
        type: 'line',
        data: ol.lower.map((d) => d.value),
        showSymbol: false,
        lineStyle: { width: 0 },
        areaStyle: { color: 'transparent' },
        stack: ol.label || 'band',
        silent: true,
      })
    }
  }

  return {
    backgroundColor: 'transparent',
    grid: { top: 40, right: 20, bottom: 60, left: 60, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#f1f5f9', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: props.yAxisLabel,
      nameTextStyle: { color: '#94a3b8', fontSize: 11 },
      axisLine: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#334155', type: 'dashed' } },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider',
        height: 20,
        bottom: 8,
        borderColor: '#334155',
        backgroundColor: '#1e293b',
        fillerColor: 'rgba(59, 130, 246, 0.2)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: '#94a3b8' },
      },
    ],
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
  () => [props.data, props.overlays, props.timeRange],
  () => {
    nextTick(renderChart)
  },
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
.base-time-series-chart {
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
