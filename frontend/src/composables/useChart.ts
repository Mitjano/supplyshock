import { ref, onMounted, onUnmounted, type Ref } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, CandlestickChart, PieChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent, ToolboxComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, BarChart, CandlestickChart, PieChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DataZoomComponent, ToolboxComponent,
  CanvasRenderer
])

const DARK_THEME: echarts.ThemeOption = {
  backgroundColor: 'transparent',
  textStyle: { color: '#a1a1aa' },
  title: { textStyle: { color: '#e2e8f0' }, subtextStyle: { color: '#a1a1aa' } },
  line: { itemStyle: { borderWidth: 2 }, lineStyle: { width: 2 }, symbolSize: 4 },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#334155' } },
    axisTick: { lineStyle: { color: '#334155' } },
    axisLabel: { color: '#a1a1aa' },
    splitLine: { lineStyle: { color: '#1e293b' } }
  },
  valueAxis: {
    axisLine: { lineStyle: { color: '#334155' } },
    axisTick: { lineStyle: { color: '#334155' } },
    axisLabel: { color: '#a1a1aa' },
    splitLine: { lineStyle: { color: '#1e293b' } }
  },
  legend: { textStyle: { color: '#a1a1aa' } },
  tooltip: {
    backgroundColor: '#1e293b',
    borderColor: '#334155',
    textStyle: { color: '#e2e8f0' }
  },
  dataZoom: {
    backgroundColor: '#0f172a',
    dataBackgroundColor: '#1e293b',
    fillerColor: 'rgba(59, 130, 246, 0.15)',
    handleColor: '#3b82f6',
    textStyle: { color: '#a1a1aa' }
  },
  candlestick: {
    itemStyle: {
      color: '#22c55e',
      color0: '#ef4444',
      borderColor: '#22c55e',
      borderColor0: '#ef4444'
    }
  }
}

echarts.registerTheme('supplyshock-dark', DARK_THEME)

export function useChart(containerRef: Ref<HTMLElement | null>) {
  const chart = ref<echarts.ECharts | null>(null)

  onMounted(() => {
    if (containerRef.value) {
      chart.value = echarts.init(containerRef.value, 'supplyshock-dark')
      window.addEventListener('resize', handleResize)
    }
  })

  onUnmounted(() => {
    chart.value?.dispose()
    window.removeEventListener('resize', handleResize)
  })

  function handleResize() {
    chart.value?.resize()
  }

  function setOption(option: echarts.EChartsOption) {
    chart.value?.setOption(option, true)
  }

  return { chart, setOption }
}
