import logging
from collections import deque

from config import settings
from kalman.engine import KalmanFilter
from models import Candle, KalmanResult, SnapshotResponse

logger = logging.getLogger(__name__)


class CandleStore:
    def __init__(self, kalman: KalmanFilter, maxlen: int = settings.CANDLE_STORE_SIZE):
        self.candles: deque[Candle] = deque(maxlen=maxlen)
        self.kalman_results: deque[KalmanResult] = deque(maxlen=maxlen)
        self.kalman = kalman

    def last_timestamp(self) -> int | None:
        if self.candles:
            return self.candles[-1].timestamp
        return None

    def add_candle(self, candle: Candle) -> KalmanResult | None:
        last_ts = self.last_timestamp()
        if last_ts is not None and candle.timestamp <= last_ts:
            logger.debug("Duplicate candle skipped: %d", candle.timestamp)
            return None

        result = self.kalman.update(candle.timestamp, candle.close)
        self.candles.append(candle)
        self.kalman_results.append(result)
        return result

    def bulk_load(self, candles: list[Candle]) -> None:
        if not candles:
            return

        self.kalman.initialize(candles[0].close)

        for candle in candles:
            result = self.kalman.update(candle.timestamp, candle.close)
            self.candles.append(candle)
            self.kalman_results.append(result)

        logger.info(
            "Bulk loaded %d candles, Kalman stabilized (P=%.4f, K=%.4f)",
            len(candles),
            self.kalman.P,
            self.kalman_results[-1].kalman_gain,
        )

    def get_snapshot(self) -> SnapshotResponse:
        return SnapshotResponse(
            candles=list(self.candles),
            kalman_results=list(self.kalman_results),
            symbol=settings.SYMBOL,
            interval=settings.INTERVAL,
            kalman_q=settings.Q,
            kalman_r=settings.R,
            k_band_1=settings.K_BAND_1,
            k_band_2=settings.K_BAND_2,
            k_band_3=settings.K_BAND_3,
        )
