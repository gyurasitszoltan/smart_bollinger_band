export interface Candle {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface KalmanResult {
  timestamp: number
  estimated_price: number
  uncertainty: number
  upper_1: number
  lower_1: number
  upper_2: number
  lower_2: number
  upper_3: number
  lower_3: number
  kalman_gain: number
  effective_r: number
  vol_z: number
}

export interface Snapshot {
  candles: Candle[]
  kalman_results: KalmanResult[]
  symbol: string
  interval: string
  kalman_q: number
  kalman_r: number
  k_band_1: number
  k_band_2: number
  k_band_3: number
  vol_enabled: boolean
  vol_beta: number
  vol_window: number
}

export type WsMessage =
  | {
      type: 'candle'
      candle: Candle
      kalman: KalmanResult
    }
  | {
      type: 'tick'
      price: number
      timestamp: number
    }
