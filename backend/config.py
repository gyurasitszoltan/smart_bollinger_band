from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bybit
    SYMBOL: str = "BTCUSDT"
    CATEGORY: str = "linear"
    INTERVAL: str = "1"
    BOOTSTRAP_CANDLES: int = 10000

    # Kalman (log-price space — árfüggetlen, minden coinra ugyanaz)
    Q: float = 1e-7       # Folyamatzaj (log-return variancia / lépés)
    R: float = 1e-4       # Mérési zaj (log-térben)
    P0: float = 1.0       # Kezdeti bizonytalanság (log-térben)
    K_BAND_1: float = 1.0  # Belső sáv (±1σ ≈ 68%)
    K_BAND_2: float = 2.0  # Közepes sáv (±2σ ≈ 95%)
    K_BAND_3: float = 3.0  # Külső sáv (±3σ ≈ 99.7%)

    # Volume-adaptív R_t
    VOL_ENABLED: bool = True       # Volume hatás be/ki kapcsoló
    VOL_WINDOW: int = 21           # EMA ablak a log-volume statisztikához
    VOL_BETA: float = 0.7          # Moduláció erőssége (0 = kikapcsolt)
    VOL_Z_MAX: float = 3.0         # Z-score clamp határ
    R_MIN_MULT: float = 0.1        # R_t alsó korlát szorzó
    R_MAX_MULT: float = 10.0        # R_t felső korlát szorzó
    VOL_SMOOTH: int = 25           # Z-score EMA simítás periódusa (1 = nincs simítás)
    VOL_EPS: float = 1e-12         # Numerikus védelem (variancia minimum)

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CANDLE_STORE_SIZE: int = 9500


settings = Settings()
