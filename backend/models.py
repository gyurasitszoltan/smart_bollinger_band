from pydantic import BaseModel


class Candle(BaseModel):
    timestamp: int  # ms
    open: float
    high: float
    low: float
    close: float
    volume: float


class KalmanResult(BaseModel):
    timestamp: int
    estimated_price: float
    uncertainty: float
    upper_1: float
    lower_1: float
    upper_2: float
    lower_2: float
    upper_3: float
    lower_3: float
    kalman_gain: float
    effective_r: float
    vol_z: float


class SnapshotResponse(BaseModel):
    candles: list[Candle]
    kalman_results: list[KalmanResult]
    symbol: str
    interval: str
    kalman_q: float
    kalman_r: float
    k_band_1: float
    k_band_2: float
    k_band_3: float
    vol_enabled: bool
    vol_beta: float
    vol_window: int
