<template>
  <div class="base-candlestick">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, type PropType } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([CandlestickChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

/* ── Types ── */
export interface OHLCPoint {
  time: number | string
  open: number
  high: number
  low: number
  close: number
}

/* ── Props ── */
const props = defineProps({
  data: {
    type: Array as PropType<OHLCPoint[]>,
    required: true,
  },
  title: {
    type: String,
    default: '',
  },
})

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function buildOptions(): echarts.EChartsOption {
  const times = props.data.map((d) => d.time)
  const ohlc = props.data.map((d) => [d.open, d.close, d.low, d.high])

  return {
    backgroundColor: 'transparent',
    grid: { top: 40, right: 20, bottom: 60, left: 60, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#f1f5f9', fontSize: 12 },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const d = p.data
        return `${p.axisValue}<br/>
          O: ${d[0]}&nbsp; H: ${d[3]}<br/>
          L: ${d[2]}&nbsp; C: ${d[1]}`
      },
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
      scale: true,
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
    series: [
      {
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#22c55e',        // bullish body
          color0: '#ef4444',       // bearish body
          borderColor: '#22c55e',  // bullish border
          borderColor0: '#ef4444', // bearish border
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

watch(() => props.data, () => nextTick(renderChart), { deep: true })

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
.base-candlestick {
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
