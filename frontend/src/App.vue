<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import CandleChart from './components/CandleChart.vue'
import StatusBar from './components/StatusBar.vue'
import { useWebSocket } from './composables/useWebSocket'
import type { Candle, KalmanResult, Snapshot } from './types'

const candles = ref<Candle[]>([])
const kalmanResults = ref<KalmanResult[]>([])
const symbol = ref('BTCUSDT')
const interval = ref('1')
const loading = ref(true)
const error = ref('')

const { status, lastMessage, connect } = useWebSocket('/ws')

const lastKalman = computed<KalmanResult | null>(() => {
  const msg = lastMessage.value
  if (msg && msg.type === 'candle') {
    return msg.kalman
  }
  if (kalmanResults.value.length > 0) {
    return kalmanResults.value[kalmanResults.value.length - 1]
  }
  return null
})

async function loadSnapshot() {
  try {
    const resp = await fetch('/api/snapshot')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data: Snapshot = await resp.json()
    candles.value = data.candles
    kalmanResults.value = data.kalman_results
    symbol.value = data.symbol
    interval.value = data.interval
    loading.value = false
  } catch (e) {
    error.value = `Failed to load snapshot: ${e}`
    loading.value = false
  }
}

onMounted(async () => {
  await loadSnapshot()
  connect()
})
</script>

<template>
  <div class="app-layout">
    <StatusBar
      :status="status"
      :symbol="symbol"
      :interval="interval"
      :last-kalman="lastKalman"
    />
    <div class="chart-wrapper">
      <div v-if="loading" class="loading">Loading historical data...</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <CandleChart
        v-else
        :candles="candles"
        :kalman-results="kalmanResults"
        :last-message="lastMessage"
      />
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
}

.chart-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.loading, .error {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  font-size: 18px;
}

.error {
  color: #ef5350;
}
</style>
