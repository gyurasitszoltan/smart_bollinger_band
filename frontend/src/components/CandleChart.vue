<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { Candle, KalmanResult, WsMessage } from '../types'

const props = defineProps<{
  candles: Candle[]
  kalmanResults: KalmanResult[]
  lastMessage: WsMessage | null
}>()

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let midLine: ISeriesApi<'Line'> | null = null
let upper1: ISeriesApi<'Line'> | null = null
let lower1: ISeriesApi<'Line'> | null = null
let upper2: ISeriesApi<'Line'> | null = null
let lower2: ISeriesApi<'Line'> | null = null
let upper3: ISeriesApi<'Line'> | null = null
let lower3: ISeriesApi<'Line'> | null = null
let rEffLine: ISeriesApi<'Line'> | null = null
let lastCandleData: { time: UTCTimestamp; open: number; high: number; low: number; close: number } | null = null

function toSec(ms: number): UTCTimestamp {
  return (ms / 1000) as UTCTimestamp
}

// Band colors: inner → outer  (progressively more transparent)
const BAND_1_COLOR = 'rgba(255, 152, 0, 0.9)'   // orange, strong
const BAND_2_COLOR = 'rgba(255, 152, 0, 0.5)'   // orange, medium
const BAND_3_COLOR = 'rgba(255, 152, 0, 0.25)'  // orange, faint

function initChart() {
  if (!chartContainer.value) return

  chart = createChart(chartContainer.value, {
    layout: {
      background: { color: '#1a1a2e' },
      textColor: '#d1d4dc',
    },
    grid: {
      vertLines: { color: '#2B2B43' },
      horzLines: { color: '#2B2B43' },
    },
    crosshair: {
      mode: 0,
    },
    timeScale: {
      timeVisible: true,
      secondsVisible: false,
    },
  })

  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderVisible: false,
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
  })

  midLine = chart.addSeries(LineSeries, {
    color: '#2196F3',
    lineWidth: 2,
  })

  // Band 1 — inner (1σ)
  upper1 = chart.addSeries(LineSeries, { color: BAND_1_COLOR, lineWidth: 1 })
  lower1 = chart.addSeries(LineSeries, { color: BAND_1_COLOR, lineWidth: 1 })

  // Band 2 — middle (2σ)
  upper2 = chart.addSeries(LineSeries, { color: BAND_2_COLOR, lineWidth: 1, lineStyle: 2 })
  lower2 = chart.addSeries(LineSeries, { color: BAND_2_COLOR, lineWidth: 1, lineStyle: 2 })

  // Band 3 — outer (3σ)
  upper3 = chart.addSeries(LineSeries, { color: BAND_3_COLOR, lineWidth: 1, lineStyle: 3 })
  lower3 = chart.addSeries(LineSeries, { color: BAND_3_COLOR, lineWidth: 1, lineStyle: 3 })

  // R_t overlay — saját skálán, chart alsó 20%-ában
  rEffLine = chart.addSeries(LineSeries, {
    color: '#8866dd',
    lineWidth: 1,
    lineStyle: 0,
    priceScaleId: 'r_eff',
    lastValueVisible: true,
    priceFormat: {
      type: 'custom',
      formatter: (val: number) => val.toExponential(1),
    },
  })

  chart.priceScale('r_eff').applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
    borderVisible: false,
    autoScale: true,
  })
}

function setLineData(series: ISeriesApi<'Line'> | null, data: { time: UTCTimestamp; value: number }[]) {
  series?.setData(data)
}

function updateLine(series: ISeriesApi<'Line'> | null, time: UTCTimestamp, value: number) {
  series?.update({ time, value })
}

function loadSnapshot() {
  if (!candleSeries || !midLine) return

  const candleData = props.candles.map((c) => ({
    time: toSec(c.timestamp),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }))

  candleSeries.setData(candleData)
  if (candleData.length > 0) {
    lastCandleData = candleData[candleData.length - 1]
  }

  const toLine = (getter: (k: KalmanResult) => number) =>
    props.kalmanResults.map((k) => ({ time: toSec(k.timestamp), value: getter(k) }))

  setLineData(midLine, toLine((k) => k.estimated_price))
  setLineData(upper1, toLine((k) => k.upper_1))
  setLineData(lower1, toLine((k) => k.lower_1))
  setLineData(upper2, toLine((k) => k.upper_2))
  setLineData(lower2, toLine((k) => k.lower_2))
  setLineData(upper3, toLine((k) => k.upper_3))
  setLineData(lower3, toLine((k) => k.lower_3))
  setLineData(rEffLine, toLine((k) => k.effective_r))

  chart?.timeScale().fitContent()
}

watch(
  () => props.lastMessage,
  (msg) => {
    if (!msg || !candleSeries || !midLine) return

    if (msg.type === 'candle') {
      const cd = {
        time: toSec(msg.candle.timestamp),
        open: msg.candle.open,
        high: msg.candle.high,
        low: msg.candle.low,
        close: msg.candle.close,
      }
      candleSeries.update(cd)
      lastCandleData = cd

      const t = toSec(msg.kalman.timestamp)
      updateLine(midLine, t, msg.kalman.estimated_price)
      updateLine(upper1, t, msg.kalman.upper_1)
      updateLine(lower1, t, msg.kalman.lower_1)
      updateLine(upper2, t, msg.kalman.upper_2)
      updateLine(lower2, t, msg.kalman.lower_2)
      updateLine(upper3, t, msg.kalman.upper_3)
      updateLine(lower3, t, msg.kalman.lower_3)
      updateLine(rEffLine, t, msg.kalman.effective_r)
    }

    if (msg.type === 'tick' && lastCandleData) {
      candleSeries.update({
        ...lastCandleData,
        close: msg.price,
        high: Math.max(lastCandleData.high, msg.price),
        low: Math.min(lastCandleData.low, msg.price),
      })
    }
  }
)

watch(
  () => props.candles,
  () => {
    if (props.candles.length > 0) {
      loadSnapshot()
    }
  }
)

function handleResize() {
  if (chart && chartContainer.value) {
    chart.applyOptions({
      width: chartContainer.value.clientWidth,
      height: chartContainer.value.clientHeight,
    })
  }
}

onMounted(() => {
  initChart()
  if (props.candles.length > 0) {
    loadSnapshot()
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.remove()
  chart = null
})
</script>

<template>
  <div ref="chartContainer" class="chart-container"></div>
</template>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>
