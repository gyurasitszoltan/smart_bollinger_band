# Volume-driven Kalman preconcept

## 1. Cel

Ez a dokumentum egy konkret, implementalhato tervet ad arra, hogyan javitsuk a jelenlegi 1D log-price Kalman becslest **relativ volumen** informacioval ugy, hogy:

- a volumen nem lesz kulon becsult allapot,
- a meglvo arhurok (price estimate + bands) megmarad,
- a model reagalasa alkalmazkodik a piac "erossegehez".

Rovid valasz:
- **Mit?** adaptiv meresi zaj (`R_t`) a relativ volumen alapjan.
- **Miert?** nagy forgalomnal gyorsabb kovetes, alacsony forgalomnal stabilabb szures.
- **Hogyan?** rolling/EMA alapu log-volume normalizalas -> z-score -> clamp -> `R_t` skala.

---

## 2. Mit valtoztatunk

### 2.1 Alapelv

A Kalman allapot tovabbra is 1D marad:

- `x_t = ln(price_t)`

Nem vezetunk be kulon volumen-allapotot. Ehelyett a volumen csak az adott lepes meresi zajat (es ezzel a Kalman gain-t) befolyasolja:

- fix `R` helyett idoben valtozo `R_t`

### 2.2 Volumen reprezentacio

Nyers abszolut volumen helyett relativ volumen jel:

1. `lv_t = log1p(volume_t)`
2. `lv_t` EMA atlag + EMA variancia
3. `z_t = (lv_t - ema_t) / sqrt(var_t + eps)`
4. `z_t` clamp: `[-Z_MAX, +Z_MAX]`

Ez dimenziomentes, stabilabb, es jobban osszehasonlithato kulonbozo idosikok/szimbólumok kozott.

### 2.3 R modulator

Javasolt forma:

- `R_t = R0 * exp(-BETA * z_t)`
- clamp: `R_t in [R0 * R_MIN_MULT, R0 * R_MAX_MULT]`

Intuicio:

- `z_t > 0` (atlag feletti volumen) -> kisebb `R_t` -> nagyobb Kalman gain -> gyorsabb kovetes
- `z_t < 0` (atlag alatti volumen) -> nagyobb `R_t` -> kisebb gain -> simabb gorbe

---

## 3. Miert ez a jo kompromisszum

1. **Nem bonyolitja tul a modellt**
   - 2D/3D allapot helyett marad a jelenlegi 1D architektura.

2. **A volumen gyakorlati szerepet kap**
   - nem "onmagat becsuljuk", hanem a becsles megbizhatosagat hangoljuk vele.

3. **Kevesebb kockazat, gyors iteracio**
   - API, frontend es chart struktura nagyreszt valtozatlan marad.

4. **Jobb piaci rezsim-kezeles**
   - trend/kitores idejen tipikusan magasabb volumen -> gyorsabb adaptacio,
   - oldalazo/alacsony volumen idejen kisebb tulreagalas.

---

## 4. Hogyan implementaljuk ebben a projektben

### 4.1 Erintett fajlok

- `backend/config.py`
- `backend/kalman/engine.py`
- `backend/store.py`
- opcionisan:
  - `backend/models.py` (debug mezok),
  - `frontend/src/types/index.ts` (ha debug mezoket kuldunk).

### 4.2 Config bovitese

Uj parameterek (kezdo default):

- `VOL_WINDOW = 50`
- `VOL_BETA = 0.7`
- `VOL_Z_MAX = 3.0`
- `R_MIN_MULT = 0.2`
- `R_MAX_MULT = 5.0`
- `VOL_EPS = 1e-12`

Megjegyzes:
- 1m candlesnel 50 jo kezdoertek,
- nagyobb timeframe-en lehet kisebb ablak is eleg.

### 4.3 Engine modositasa

`KalmanFilter` belso allapot bovitese minimalisan:

- `base_R` (az eredeti `R0`)
- `vol_ema`, `vol_var`, `vol_initialized`

`update(timestamp, measurement, volume)` folyamat:

1. `z_price = log(measurement)`
2. `z_vol = log1p(volume)`
3. EMA/variancia frissites `z_vol`-ra
4. relativ volumen `z_t` szamitas + clamp
5. `R_t` szamitas + clamp
6. standard 1D Kalman predict/update, de `R_t`-vel:
   - `K = P_pred / (P_pred + R_t)`
7. kimenet ugyanaz marad (`estimated_price`, savok, gain, P)

Opcionális debug:
- `effective_r`, `vol_z` visszaadasa `KalmanResult`-ban.

### 4.4 Store modositasa

`store.py`:

- `self.kalman.update(candle.timestamp, candle.close, candle.volume)`

Mind `add_candle`, mind `bulk_load` ezt hasznalja.

### 4.5 API/Frontend kompatibilitas

Alap esetben nincs schema torés:

- `KalmanResult` maradhat valtozatlan,
- frontend chart valtoztatas nelkul fut.

Ha debug mezok mennek:
- backend model + frontend type bovitese kell.

---

## 5. Pseudocode

```python
lv = math.log1p(volume)

if not vol_initialized:
    vol_ema = lv
    vol_var = 1e-6
    vol_initialized = True
else:
    alpha = 2.0 / (VOL_WINDOW + 1.0)
    delta = lv - vol_ema
    vol_ema = vol_ema + alpha * delta
    vol_var = (1.0 - alpha) * vol_var + alpha * (delta * delta)

vol_std = math.sqrt(max(vol_var, VOL_EPS))
vol_z = (lv - vol_ema) / vol_std
vol_z = clamp(vol_z, -VOL_Z_MAX, VOL_Z_MAX)

R_t = base_R * math.exp(-VOL_BETA * vol_z)
R_t = clamp(R_t, base_R * R_MIN_MULT, base_R * R_MAX_MULT)

K = P_pred / (P_pred + R_t)
```

---

## 6. Tesztelesi terv

### 6.1 Unit szint (engine)

1. **Stabilitas**: `R_t` mindig pozitiv es clamp-en belul.
2. **Monoton viselkedes**: nagyobb `vol_z` -> kisebb `R_t`.
3. **No NaN/Inf**: extrem volumeneknel sincs numerikus problema.
4. **Backward-compat**: ha `VOL_BETA=0`, akkor fix-R viselkedeshez kozelit.

### 6.2 Integracios szint

1. Bootstrap lefut hiba nelkul.
2. Live candle frissitesnel nincs schema/serializer hiba.
3. Frontend chart rendering valtozatlanul mukodik.

### 6.3 Viselkedesi ellenorzes

Replay/elo streamen nezzuk:

- kitoreseknel gyorsabb kozepvonal kovetes,
- csendes idoszakban kevesebb zajos ugralas,
- sávok konzisztens geometriaval maradnak.

---

## 7. Parameter tuning guide

Tuningsorrend:

1. `VOL_BETA` (hatas erossege)
   - tul magas -> ideges kovetes,
   - tul alacsony -> nincs erdemi hatas.

2. `VOL_WINDOW` (memoria hossza)
   - rovid ablak -> gyors, de zajos z-score,
   - hosszu ablak -> stabil, de lassabb rezsimkovetes.

3. `R_MIN_MULT` / `R_MAX_MULT`
   - vedokorlat, hogy ne essen tul alacsonyra/tul magasra a gain.

Praktikus kezdes:

- `VOL_WINDOW=50`, `VOL_BETA=0.7`, `R_MIN_MULT=0.2`, `R_MAX_MULT=5.0`.

---

## 8. Kockazatok es vedelmek

1. **Volumen spike manipulacio / outlier**
   - vedekezes: `log1p`, z-clamp, `R_t` clamp.

2. **Korai warmup torzitas**
   - vedekezes: bootstrap alatt EMA/var feltoltese;
   - alternativ: elso `N` barban gyengitett modulacio.

3. **Tul sok uj hyperparameter**
   - vedekezes: eros defaultok + tuning protokoll + optional feature flag.

---

## 9. Rollout strategia

1. **Phase 1 (safe)**: backend-only valtozas, nincs frontend schema modositas.
2. **Phase 2 (debug)**: opcionisan `effective_r` + `vol_z` kimenet a status/debug nezethez.
3. **Phase 3 (tuning)**: historikus replay + elo monitorozas alapjan parameter finomitas.

Rollback egyszeru:

- `VOL_BETA=0` -> volumenhatas gyakorlatilag kikapcsolva.

---

## 10. Donto javaslat

Implementaljuk a volumen-hatast **adaptiv `R_t`** formaban relativ log-volume z-score alapjan.

Ez adja a legjobb ar/ertek aranyt:

- erdemi minoseg-javulas varhato trend/kitoresekben,
- alacsony implementacios kockazat,
- teljes kompatibilitas a jelenlegi 1D Kalman es chart pipeline-nal.
