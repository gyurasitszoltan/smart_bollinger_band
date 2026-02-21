<script setup lang="ts">
import { computed } from 'vue'
import type { KalmanResult } from '../types'

const props = defineProps<{
  status: 'connecting' | 'connected' | 'disconnected'
  symbol: string
  interval: string
  lastKalman: KalmanResult | null
}>()

const volClass = computed(() => {
  if (!props.lastKalman) return ''
  const vz = props.lastKalman.vol_z
  if (vz > 0.5) return 'vol-high'
  if (vz < -0.5) return 'vol-low'
  return 'vol-neutral'
})
</script>

<template>
  <div class="status-bar">
    <div class="status-left">
      <span class="symbol">{{ symbol }} {{ interval }}m</span>
      <span class="dot" :class="status"></span>
      <span class="status-text">{{ status }}</span>
    </div>
    <div v-if="lastKalman" class="status-right">
      <span>Est: <b>{{ lastKalman.estimated_price.toFixed(4) }}</b></span>
      <span class="sep">|</span>
      <span class="band band-1">B1: {{ lastKalman.lower_1.toFixed(4) }} – {{ lastKalman.upper_1.toFixed(4) }}</span>
      <span class="sep">|</span>
      <span class="band band-2">B2: {{ lastKalman.lower_2.toFixed(4) }} – {{ lastKalman.upper_2.toFixed(4) }}</span>
      <span class="sep">|</span>
      <span class="band band-3">B3: {{ lastKalman.lower_3.toFixed(4) }} – {{ lastKalman.upper_3.toFixed(4) }}</span>
      <span class="sep">|</span>
      <span>K: {{ lastKalman.kalman_gain.toFixed(6) }}</span>
      <span class="sep">|</span>
      <span>P: {{ lastKalman.uncertainty.toExponential(2) }}</span>
      <span class="sep">|</span>
      <span :class="volClass">R: {{ lastKalman.effective_r.toExponential(2) }}</span>
      <span class="sep">|</span>
      <span :class="volClass">Vz: {{ lastKalman.vol_z.toFixed(2) }}</span>
    </div>
  </div>
</template>

<style scoped>
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #16213e;
  color: #d1d4dc;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  border-bottom: 1px solid #2B2B43;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.symbol {
  font-weight: bold;
  color: #fff;
  font-size: 15px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot.connected {
  background: #26a69a;
}

.dot.connecting {
  background: #FF9800;
}

.dot.disconnected {
  background: #ef5350;
}

.status-text {
  text-transform: capitalize;
}

.status-right {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.sep {
  color: #555;
}

b {
  color: #fff;
}

.band-1 {
  color: rgba(255, 152, 0, 0.95);
}

.band-2 {
  color: rgba(255, 152, 0, 0.65);
}

.band-3 {
  color: rgba(255, 152, 0, 0.4);
}

.vol-high {
  color: #26a69a;
}

.vol-neutral {
  color: #888;
}

.vol-low {
  color: #ef5350;
}
</style>
