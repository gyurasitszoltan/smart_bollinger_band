# Volume-adaptív R_t implementációs terv (V1)

## Összefoglaló

A jelenlegi fix `R` (mérési zaj) paramétert időben változó `R_t`-re cseréljük.
A relatív volumen z-score alapján moduláljuk: nagy volumen → kisebb R → gyorsabb
ár-követés, alacsony volumen → nagyobb R → simább szűrés.

A Kalman állapot 1D marad (`ln(price)`), a volumen NEM állapotváltozó, hanem
a szűrő bizalmi paramétere (mérési zaj modulátor).

---

## 1. lépés — `backend/config.py` bővítése

### Feladat

Új paraméterek hozzáadása a `Settings` osztályhoz.

### Módosítás

```python
class Settings(BaseSettings):
    # ... meglévő paraméterek ...

    # ── Volume-adaptív R_t paraméterek ──
    VOL_ENABLED: bool = True       # Volume hatás be/ki kapcsoló
    VOL_WINDOW: int = 50           # EMA ablak (periódus) a log-volume statisztikához
    VOL_BETA: float = 0.7          # Moduláció erőssége (0 = kikapcsolt)
    VOL_Z_MAX: float = 3.0         # Z-score clamp határ
    R_MIN_MULT: float = 0.2        # R_t alsó korlát: R_base * R_MIN_MULT
    R_MAX_MULT: float = 5.0        # R_t felső korlát: R_base * R_MAX_MULT
    VOL_EPS: float = 1e-12         # Numerikus védelem (variancia minimum)
```

### Megjegyzések

- `VOL_ENABLED = False` vagy `VOL_BETA = 0.0` → teljes rollback, fix R viselkedés.
- A meglévő `R` paraméter lesz a `base_R` (R₀).

---

## 2. lépés — `backend/kalman/engine.py` módosítása

### Feladat

A `KalmanFilter` osztály bővítése volumen EMA statisztikával és adaptív R_t
számítással. A fő update ciklus a mérési zajt dinamikusan változtatja.

### Jelenlegi szignátúra

```python
def __init__(self, Q, R, P0, k_band_1, k_band_2, k_band_3):
def update(self, timestamp: int, measurement: float) -> KalmanResult:
```

### Új szignátúra

```python
def __init__(self, Q, R, P0, k_band_1, k_band_2, k_band_3,
             vol_enabled, vol_window, vol_beta, vol_z_max,
             r_min_mult, r_max_mult, vol_eps):

def update(self, timestamp: int, measurement: float, volume: float = 0.0) -> KalmanResult:
```

### Részletes módosítás

#### 2a. Új belső állapot (`__init__`)

```python
# Volume-adaptív R paraméterek
self.vol_enabled = vol_enabled
self.vol_beta = vol_beta
self.vol_z_max = vol_z_max
self.r_min_mult = r_min_mult
self.r_max_mult = r_max_mult
self.vol_eps = vol_eps
self.vol_alpha = 2.0 / (vol_window + 1.0)   # EMA decay faktor

# Volume EMA belső állapot
self.base_R = R                # Eredeti R megőrzése
self.vol_ema: float = 0.0      # log-volume EMA átlag
self.vol_var: float = 1e-6     # log-volume EMA variancia
self.vol_initialized: bool = False
```

#### 2b. Volume z-score számítás (privát segédmetódus)

```python
def _update_volume_stats(self, volume: float) -> float:
    """
    Frissíti a volume EMA statisztikát és visszaadja a clampelt z-score-t.

    Lépések:
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
```

#### 2c. R_t moduláció (privát segédmetódus)

```python
def _compute_effective_R(self, vol_z: float) -> float:
    """
    R_t = R_base * exp(-beta * z_t)

    Intuíció:
      z > 0 (átlag feletti volume) → R csökken → nagyobb gain → gyorsabb követés
      z < 0 (átlag alatti volume) → R nő → kisebb gain → simább görbe

    Clamp: [R_base * R_MIN_MULT, R_base * R_MAX_MULT]
    """
    R_t = self.base_R * math.exp(-self.vol_beta * vol_z)

    r_min = self.base_R * self.r_min_mult
    r_max = self.base_R * self.r_max_mult

    return max(r_min, min(R_t, r_max))
```

#### 2d. Az `update()` metódus módosítása

```python
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

    # ── Predict (random walk: F=1) ──
    x_pred = self.x
    P_pred = self.P + self.Q

    # ── Update (effective_R helyett fix R) ──
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
```

### Megjegyzés

- A `volume` paraméter default `0.0` → ha valaki `volume` nélkül hívja,
  a régi viselkedés marad (backward compat).
- Az `initialize()` és `reset()` most a volume EMA-t is nullázza:

```python
def initialize(self, first_price: float) -> None:
    self.x = math.log(first_price)
    self.P = self.P0
    self._initialized = True
    self.vol_ema = 0.0
    self.vol_var = 1e-6
    self.vol_initialized = False
```

---

## 3. lépés — `backend/models.py` bővítése

### Feladat

A `KalmanResult`-ba 2 debug mező kerül (`effective_r`, `vol_z`), ami
segíti a monitorozást és a paraméter-hangolást. A `SnapshotResponse`-ba
a volume konfiguráció.

### Módosítás

```python
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
    effective_r: float        # ← ÚJ: aktuális R_t érték
    vol_z: float              # ← ÚJ: relatív volume z-score


class SnapshotResponse(BaseModel):
    candles: list[Candle]
    kalman_results: list[KalmanResult]
    symbol: str
    interval: str
    kalman_q: float
    kalman_r: float           # base R (R₀)
    k_band_1: float
    k_band_2: float
    k_band_3: float
    vol_enabled: bool         # ← ÚJ
    vol_beta: float           # ← ÚJ
    vol_window: int           # ← ÚJ
```

---

## 4. lépés — `backend/store.py` módosítása

### Feladat

A `volume` átadása a Kalman update hívásoknak. A snapshot meta bővítése.

### Módosítás

`add_candle()`:
```python
def add_candle(self, candle: Candle) -> KalmanResult | None:
    # ... duplicate check ...
    result = self.kalman.update(candle.timestamp, candle.close, candle.volume)  # ← volume hozzáadva
    self.candles.append(candle)
    self.kalman_results.append(result)
    return result
```

`bulk_load()`:
```python
def bulk_load(self, candles: list[Candle]) -> None:
    if not candles:
        return
    self.kalman.initialize(candles[0].close)
    for candle in candles:
        result = self.kalman.update(candle.timestamp, candle.close, candle.volume)  # ← volume hozzáadva
        self.candles.append(candle)
        self.kalman_results.append(result)
    # ... logging ...
```

`get_snapshot()`:
```python
def get_snapshot(self) -> SnapshotResponse:
    return SnapshotResponse(
        # ... meglévő mezők ...
        vol_enabled=settings.VOL_ENABLED,    # ← ÚJ
        vol_beta=settings.VOL_BETA,          # ← ÚJ
        vol_window=settings.VOL_WINDOW,      # ← ÚJ
    )
```

---

## 5. lépés — `backend/main.py` módosítása

### Feladat

A `KalmanFilter` konstruktor bővítése a volume paraméterekkel.
A `/api/config` endpoint bővítése.

### Módosítás

Globális `kalman` objektum:
```python
kalman = KalmanFilter(
    Q=settings.Q,
    R=settings.R,
    P0=settings.P0,
    k_band_1=settings.K_BAND_1,
    k_band_2=settings.K_BAND_2,
    k_band_3=settings.K_BAND_3,
    vol_enabled=settings.VOL_ENABLED,     # ← ÚJ
    vol_window=settings.VOL_WINDOW,       # ← ÚJ
    vol_beta=settings.VOL_BETA,           # ← ÚJ
    vol_z_max=settings.VOL_Z_MAX,         # ← ÚJ
    r_min_mult=settings.R_MIN_MULT,       # ← ÚJ
    r_max_mult=settings.R_MAX_MULT,       # ← ÚJ
    vol_eps=settings.VOL_EPS,             # ← ÚJ
)
```

Config endpoint:
```python
@app.get("/api/config")
async def get_config():
    return {
        # ... meglévő mezők ...
        "vol_enabled": settings.VOL_ENABLED,
        "vol_beta": settings.VOL_BETA,
        "vol_window": settings.VOL_WINDOW,
        "vol_z_max": settings.VOL_Z_MAX,
        "r_min_mult": settings.R_MIN_MULT,
        "r_max_mult": settings.R_MAX_MULT,
    }
```

---

## 6. lépés — Frontend típusok frissítése

### Feladat

`frontend/src/types/index.ts` bővítése az új mezőkkel.

### Módosítás

```typescript
export interface KalmanResult {
  timestamp: number
  estimated_price: number
  uncertainty: number
  upper_1: number; lower_1: number
  upper_2: number; lower_2: number
  upper_3: number; lower_3: number
  kalman_gain: number
  effective_r: number          // ← ÚJ
  vol_z: number                // ← ÚJ
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
  vol_enabled: boolean         // ← ÚJ
  vol_beta: number             // ← ÚJ
  vol_window: number           // ← ÚJ
}
```

---

## 7. lépés — `frontend/src/components/StatusBar.vue` bővítése

### Feladat

Két új debug mező megjelenítése a StatusBar-ban:
`R_eff` (az aktuális effektív R érték) és `Vz` (a volume z-score).

### Módosítás

A `status-right` div végéhez (a `P:` mező után):

```html
<span class="sep">|</span>
<span class="vol-indicator" :class="volClass">
  Rₑ: {{ lastKalman.effective_r.toExponential(2) }}
</span>
<span class="sep">|</span>
<span class="vol-indicator" :class="volClass">
  Vz: {{ lastKalman.vol_z.toFixed(2) }}
</span>
```

Ahol `volClass` egy computed, ami a vol_z előjele alapján színez:

```typescript
const volClass = computed(() => {
  if (!props.lastKalman) return ''
  const vz = props.lastKalman.vol_z
  if (vz > 0.5) return 'vol-high'     // zöld (gyorsabb követés)
  if (vz < -0.5) return 'vol-low'     // piros (simább szűrés)
  return 'vol-neutral'                 // szürke (normál)
})
```

CSS:

```css
.vol-high    { color: #26a69a; }   /* zöld — magas volumen, gyors követés */
.vol-neutral { color: #888; }       /* szürke — átlagos volumen */
.vol-low     { color: #ef5350; }   /* piros — alacsony volumen, simított */
```

---

## 8. lépés — Build + tesztelés

### 8a. Unit teszt (engine)

Python REPL-ben ellenőrizhető:

```python
from kalman.engine import KalmanFilter

kf = KalmanFilter(
    Q=1e-7, R=1e-4, P0=1.0,
    k_band_1=1.0, k_band_2=2.0, k_band_3=3.0,
    vol_enabled=True, vol_window=50, vol_beta=0.7,
    vol_z_max=3.0, r_min_mult=0.2, r_max_mult=5.0, vol_eps=1e-12,
)

# 1. Normál volumen → R közel base-hez
r1 = kf.update(1000, 170.0, volume=50000)
print(f"Normal vol  — R_eff: {r1.effective_r:.2e}, vol_z: {r1.vol_z:.3f}")

# 2. Magas volumen → R csökken, gain nő
r2 = kf.update(2000, 171.0, volume=500000)
print(f"High vol    — R_eff: {r2.effective_r:.2e}, vol_z: {r2.vol_z:.3f}")

# 3. Alacsony volumen → R nő, gain csökken
r3 = kf.update(3000, 170.5, volume=5000)
print(f"Low vol     — R_eff: {r3.effective_r:.2e}, vol_z: {r3.vol_z:.3f}")

# Ellenőrzések:
assert r2.effective_r < r1.effective_r, "Magas volumen → kisebb R"
assert r3.effective_r > r1.effective_r, "Alacsony volumen → nagyobb R"
assert r2.kalman_gain > r3.kalman_gain, "Magas vol → nagyobb gain"
assert r1.effective_r >= kf.base_R * kf.r_min_mult, "R_min korlát"
assert r1.effective_r <= kf.base_R * kf.r_max_mult, "R_max korlát"
```

### 8b. Rollback teszt

```python
# VOL_BETA = 0 → hatás semleges
kf_off = KalmanFilter(
    Q=1e-7, R=1e-4, P0=1.0,
    k_band_1=1.0, k_band_2=2.0, k_band_3=3.0,
    vol_enabled=True, vol_window=50, vol_beta=0.0,  # ← kikapcsolt
    vol_z_max=3.0, r_min_mult=0.2, r_max_mult=5.0, vol_eps=1e-12,
)
r = kf_off.update(1000, 170.0, volume=999999)
assert abs(r.effective_r - 1e-4) < 1e-15, "Beta=0 → R marad fix"
```

### 8c. Frontend build

```bash
cd frontend
npx vue-tsc --noEmit   # TypeScript ellenőrzés
npx vite build          # Production build
```

### 8d. Integrációs teszt

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Majd másik terminálban:
curl -s http://localhost:8000/api/snapshot | python -m json.tool | head -50
# Ellenőrzés: effective_r és vol_z megjelenik a kalman_results-ban
```

---

## 9. Érintett fájlok összefoglalója

| Fájl | Változás típusa | Kockázat |
|------|----------------|----------|
| `backend/config.py` | 7 új paraméter | Alacsony |
| `backend/kalman/engine.py` | __init__ bővítés, 2 új privát metódus, update módosítás | Közepes |
| `backend/models.py` | 2 mező KalmanResult-ba, 3 mező SnapshotResponse-ba | Alacsony |
| `backend/store.py` | volume átadás update hívásokba, snapshot meta | Alacsony |
| `backend/main.py` | KalmanFilter konstruktor + /api/config bővítés | Alacsony |
| `frontend/src/types/index.ts` | 2+3 új mező a típusokba | Alacsony |
| `frontend/src/components/StatusBar.vue` | R_eff + Vz kijelzés + színkódolás | Alacsony |

Frontend chart (`CandleChart.vue`) → **NEM VÁLTOZIK** (a sávok ugyan úgy működnek).

---

## 10. Végrehajtási sorrend

```
1. config.py         — paraméterek (nincs függőség)
2. models.py         — adatmodellek (nincs függőség)
3. kalman/engine.py  — az érdemi logika (függ: models)
4. store.py          — volume átadás (függ: engine, models)
5. main.py           — konstruktor + API (függ: config, engine, store)
6. types/index.ts    — frontend típusok (függ: models)
7. StatusBar.vue     — UI (függ: types)
8. Build + teszt     — ellenőrzés
```

Lépésenként tesztelhető, minden lépés után érdemes `vue-tsc` / quick backend tesztet futtatni.

---

## 11. Rollback stratégia

Három szintű rollback:

1. **Soft**: `VOL_BETA = 0.0` a config-ban → `exp(-0 * z) = 1` → `R_t = R_base` mindig. Teljes eredeti viselkedés, kódváltoztatás nélkül.

2. **Feature flag**: `VOL_ENABLED = False` → az engine átugorja a volume számítást, fix R-t használ.

3. **Hard**: git revert → a 2 új mező (`effective_r`, `vol_z`) eltávolítása a modellből. Csak ha a feature végleg nem kell.

---

## 12. Várható viselkedés

### Normál piac (oldalazás, átlagos volumen)
- `vol_z ≈ 0` → `R_t ≈ R_base` → változatlan viselkedés a jelenlegi rendszerhez képest.

### Kitörés / nagy volumen spike
- `vol_z > 0` (tipikusan +1…+3) → `R_t < R_base` → Kalman gain nő → a középvonal gyorsabban követi az árat → a sávok hamarabb "lépnek".

### Csendes/éjszakai piac
- `vol_z < 0` (tipikusan -1…-2) → `R_t > R_base` → gain csökken → simább görbe, kevesebb zajos ugrálás.

### Extrém spike (pl. wash trading)
- `z_t` clampelődik `±Z_MAX`-ra → `R_t` clampelődik `[R_MIN_MULT, R_MAX_MULT]` korlátok közé → védelem a túlreagálás ellen.

---

## 13. Későbbi fejlesztési lehetőségek

Ha a V1 stabilan működik:

1. **Volume histogram a charton** — `CandleChart.vue`-ban lightweight-charts histogram series a volume z-score-nak.
2. **R_t overlay vonal** — az effektív R idősor vizualizálása a charton.
3. **Warmup finomítás** — bootstrap első `VOL_WINDOW` barján csökkentett `VOL_BETA`.
4. **V2 evolúció** — ha szükséges, a volume EMA statisztika közvetlenül felhasználható egy 2D modellben.
