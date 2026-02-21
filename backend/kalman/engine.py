import math
from models import KalmanResult


class KalmanFilter:
    """
    Egydimenziós Kalman-szűrő LOG-ÁR térben, 3 sávpárral.

    A szűrő ln(price)-on dolgozik, így Q és R dimenziómentes
    (log-return variancia egységben). A kimenet visszakonvertálódik
    valós ártérbe, a sávok multiplikatívak (százalékosak).

    Három sávpár (K_BAND_1/2/3) egyetlen szűrőfutásból:
      - Belső (1σ) — gyakori érintés, rövid távú volatilitás
      - Közepes (2σ) — standard Bollinger
      - Külső (3σ) — ritkán törik át, erős jelzés
    """

    def __init__(
        self,
        Q: float,
        R: float,
        P0: float,
        k_band_1: float,
        k_band_2: float,
        k_band_3: float,
    ):
        self.Q = Q
        self.R = R
        self.P0 = P0
        self.k_bands = (k_band_1, k_band_2, k_band_3)
        self.x: float = 0.0
        self.P: float = P0
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self, first_price: float) -> None:
        self.x = math.log(first_price)
        self.P = self.P0
        self._initialized = True

    def update(self, timestamp: int, measurement: float) -> KalmanResult:
        if not self._initialized:
            self.initialize(measurement)

        z = math.log(measurement)

        # ── Predict (random walk in log-space: F=1) ──
        x_pred = self.x
        P_pred = self.P + self.Q

        # ── Update ──
        K = P_pred / (P_pred + self.R)
        self.x = x_pred + K * (z - x_pred)
        self.P = (1.0 - K) * P_pred

        # ── Bands: 3 pairs from same √P ──
        sqrt_P = math.sqrt(self.P)
        estimated_price = math.exp(self.x)

        k1, k2, k3 = self.k_bands

        return KalmanResult(
            timestamp=timestamp,
            estimated_price=estimated_price,
            uncertainty=self.P,
            upper_1=math.exp(self.x + k1 * sqrt_P),
            lower_1=math.exp(self.x - k1 * sqrt_P),
            upper_2=math.exp(self.x + k2 * sqrt_P),
            lower_2=math.exp(self.x - k2 * sqrt_P),
            upper_3=math.exp(self.x + k3 * sqrt_P),
            lower_3=math.exp(self.x - k3 * sqrt_P),
            kalman_gain=K,
        )

    def reset(self, first_price: float) -> None:
        self.initialize(first_price)
