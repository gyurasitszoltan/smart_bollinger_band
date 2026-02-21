import math
from models import KalmanResult


class KalmanFilter:
    """
    Egydimenziós Kalman-szűrő LOG-ÁR térben, 3 sávpárral,
    volume-adaptív mérési zajjal (R_t).

    A szűrő ln(price)-on dolgozik, így Q és R dimenziómentes
    (log-return variancia egységben). A kimenet visszakonvertálódik
    valós ártérbe, a sávok multiplikatívak (százalékosak).

    Volume hatás:
      - Relatív volume z-score (EMA alapú log-volume normalizálás)
      - R_t = R_base * exp(-beta * z_vol)
      - Nagy volumen → kisebb R → nagyobb gain → gyorsabb követés
      - Alacsony volumen → nagyobb R → kisebb gain → simább görbe
    """

    def __init__(
        self,
        Q: float,
        R: float,
        P0: float,
        k_band_1: float,
        k_band_2: float,
        k_band_3: float,
        vol_enabled: bool = True,
        vol_window: int = 50,
        vol_beta: float = 0.7,
        vol_z_max: float = 3.0,
        r_min_mult: float = 0.2,
        r_max_mult: float = 5.0,
        vol_eps: float = 1e-12,
    ):
        self.Q = Q
        self.base_R = R
        self.P0 = P0
        self.k_bands = (k_band_1, k_band_2, k_band_3)

        # Volume-adaptív R paraméterek
        self.vol_enabled = vol_enabled
        self.vol_beta = vol_beta
        self.vol_z_max = vol_z_max
        self.r_min_mult = r_min_mult
        self.r_max_mult = r_max_mult
        self.vol_eps = vol_eps
        self.vol_alpha = 2.0 / (vol_window + 1.0)

        # Kalman belső állapot
        self.x: float = 0.0
        self.P: float = P0
        self._initialized = False

        # Volume EMA belső állapot
        self.vol_ema: float = 0.0
        self.vol_var: float = 1e-6
        self.vol_initialized: bool = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self, first_price: float) -> None:
        self.x = math.log(first_price)
        self.P = self.P0
        self._initialized = True
        self.vol_ema = 0.0
        self.vol_var = 1e-6
        self.vol_initialized = False

    def _update_volume_stats(self, volume: float) -> float:
        """
        Frissíti a volume EMA statisztikát és visszaadja a clampelt z-score-t.

        1. lv = log1p(volume)         — log-transzformáció, heavy-tail kezelés
        2. EMA átlag + variancia frissítés
        3. z = (lv - ema) / std       — standardizált relatív volumen
        4. clamp [-Z_MAX, +Z_MAX]     — outlier védelem
        """
        lv = math.log1p(volume)

        if not self.vol_initialized:
            self.vol_ema = lv
            self.vol_var = 1e-6
            self.vol_initialized = True
            return 0.0  # Első lépésnél nincs referencia → semleges

        alpha = self.vol_alpha
        delta = lv - self.vol_ema
        self.vol_ema += alpha * delta
        self.vol_var = (1.0 - alpha) * self.vol_var + alpha * (delta * delta)

        vol_std = math.sqrt(max(self.vol_var, self.vol_eps))
        z = (lv - self.vol_ema) / vol_std

        return max(-self.vol_z_max, min(z, self.vol_z_max))

    def _compute_effective_R(self, vol_z: float) -> float:
        """
        R_t = R_base * exp(-beta * z_t)

        z > 0 (átlag feletti volume) → R csökken → nagyobb gain → gyorsabb követés
        z < 0 (átlag alatti volume) → R nő → kisebb gain → simább görbe

        Clamp: [R_base * R_MIN_MULT, R_base * R_MAX_MULT]
        """
        R_t = self.base_R * math.exp(-self.vol_beta * vol_z)

        r_min = self.base_R * self.r_min_mult
        r_max = self.base_R * self.r_max_mult

        return max(r_min, min(R_t, r_max))

    def update(self, timestamp: int, measurement: float, volume: float = 0.0) -> KalmanResult:
        if not self._initialized:
            self.initialize(measurement)

        z = math.log(measurement)

        # ── Volume-adaptív R_t ──
        if self.vol_enabled and volume > 0:
            vol_z = self._update_volume_stats(volume)
            effective_R = self._compute_effective_R(vol_z)
        else:
            vol_z = 0.0
            effective_R = self.base_R

        # ── Predict (random walk in log-space: F=1) ──
        x_pred = self.x
        P_pred = self.P + self.Q

        # ── Update ──
        K = P_pred / (P_pred + effective_R)
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
            effective_r=effective_R,
            vol_z=vol_z,
        )

    def reset(self, first_price: float) -> None:
        self.initialize(first_price)
