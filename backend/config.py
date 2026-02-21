from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bybit
    SYMBOL: str = "BTCUSDT"
    CATEGORY: str = "linear"
    INTERVAL: str = "1"
    BOOTSTRAP_CANDLES: int = 1000

    # Kalman (log-price space — árfüggetlen, minden coinra ugyanaz)
    Q: float = 1e-7       # Folyamatzaj (log-return variancia / lépés)
    R: float = 1e-4       # Mérési zaj (log-térben)
    P0: float = 1.0       # Kezdeti bizonytalanság (log-térben)
    K_BAND_1: float = 1.0  # Belső sáv (±1σ ≈ 68%)
    K_BAND_2: float = 2.0  # Közepes sáv (±2σ ≈ 95%)
    K_BAND_3: float = 3.0  # Külső sáv (±3σ ≈ 99.7%)

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CANDLE_STORE_SIZE: int = 800


settings = Settings()
