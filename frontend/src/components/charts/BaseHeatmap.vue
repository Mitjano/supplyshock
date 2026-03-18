<template>
  <div class="base-heatmap">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, type PropType } from 'vue'
import * as echarts from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

/* ── Props ── */
const props = defineProps({
  /** 2D matrix: data[row][col] or flat array of [xIdx, yIdx, value] */
  data: {
    type: Array as PropType<number[][] | [number, number, number][]>,
    required: true,
  },
  xLabels: {
    type: Array as PropType<string[]>,
    required: true,
  },
  yLabels: {
    type: Array as PropType<string[]>,
    required: true,
  },
  title: {
    type: String,
    default: '',
  },
  colorRange: {
    type: Array as PropType<[string, string]>,
    default: () => ['#1e293b', '#3b82f6'],
  },
})

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function normalizeData(): [number, number, number][] {
  if (!props.data.length) return []
  // If first element has 3 items, assume flat [x, y, val]
  if (Array.isArray(props.data[0]) && (props.data[0] as number[]).length === 3) {
    return props.data as [number, number, number][]
  }
  // Convert matrix to flat
  const flat: [number, number, number][] = []
  for (let y = 0; y < props.data.length; y++) {
    const row = props.data[y] as number[]
    for (let x = 0; x < row.length; x++) {
      flat.push([x, y, row[x]])
    }
  }
  return flat
}

function buildOptions(): echarts.EChartsOption {
  const flat = normalizeData()
  const allValues = flat.map((d) => d[2])
  const min = allValues.length ? Math.min(...allValues) : 0
  const max = allValues.length ? Math.max(...allValues) : 1

  return {
    backgroundColor: 'transparent',
    grid: { top: 30, right: 80, bottom: 40, left: 80, containLabel: true },
    tooltip: {
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#f1f5f9', fontSize: 12 },
      formatter: (params: any) => {
        const d = params.data
        return `${props.xLabels[d[0]]} / ${props.yLabels[d[1]]}<br/>Value: <b>${d[2]}</b>`
      },
    },
    xAxis: {
      type: 'category',
      data: props.xLabels,
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitArea: { show: false },
    },
    yAxis: {
      type: 'category',
      data: props.yLabels,
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitArea: { show: false },
    },
    visualMap: {
      min,
      max,
      calculable: true,
      orient: 'vertical',
      right: 0,
      top: 'center',
      inRange: { color: props.colorRange as string[] },
      textStyle: { color: '#94a3b8' },
    },
    series: [
      {
        type: 'heatmap',
        data: flat,
        emphasis: {
          itemStyle: { borderColor: '#f8fafc', borderWidth: 1 },
        },
        itemStyle: {
          borderColor: '#0f172a',
          borderWidth: 1,
        },
      },
    ],
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
  () => [props.data, props.xLabels, props.yLabels, props.colorRange],
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
.base-heatmap {
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
