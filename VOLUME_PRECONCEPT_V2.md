# Volume-in-state Kalman preconcept (2D)

## 1. Cel

Ez a dokumentum egy konkret tervet ad arra az esetre, ha a Kalman szuro allapotvektorat 2D-re bovitenenk, es a volument is **becsulni** szeretnenk.

Rovid valasz:

- **Mit?** 2D Kalman: `x_t = [ln(price_t), ln(volume_t)]^T`.
- **Miert?** lehetoseg az ar-volumen egyuttmozgas (korrelacio) explicit modellezesere, rezsim/likviditas-jelleg becslesere, es stabilabb alkalmazkodasra.
- **Hogyan?** 2x2 allapotkovetesi es meresi modell (`F`, `H`, `Q`, `R`), 2x2 inverzio, a savok tovabbra is a price komponens bizonytalansagabol jonnek.

Megjegyzes: ez a megkozelites bonyolultabb es tobb parametert igenyel; gyakorlati haszna tipikusan akkor jon ki, ha a volumennel kapcsolatos zajokat/korrelaciot is tudjuk ertelmesen hangolni.

---

## 2. Mit valtoztatunk

### 2.1 Allapot es meres definicio

Allapot (2D):

- `x_t = [p_t, v_t]^T`
- `p_t = ln(close_t)`
- `v_t = ln(volume_t + eps)` vagy `ln(1 + volume_t)` (log1p)

Meres (2D):

- `z_t = [ln(close_t), ln(volume_t + eps)]^T`

### 2.2 Atmeneti (dinamikai) modell

Legkonzervativabb (random walk):

- `x_t = F x_{t-1} + w_t`, ahol `F = I_2`
- `w_t ~ N(0, Q)`

Opcio, ha gyenge csatolast akarunk (rezsim/atfolyas):

- `F = [[1, f_pv], [f_vp, 1]]` kis csatolasi tagokkal

Kezdesnek erosen javasolt: `F = I_2`.

### 2.3 Megfigyelesi modell

Egyszeru (kozvetlen meres):

- `z_t = H x_t + n_t`, ahol `H = I_2`
- `n_t ~ N(0, R)`

Ez akkor jo, ha a volume meres "ugyanaz a jel" mint a modell masodik komponense (log-volume).

### 2.4 Q es R szerkezete

Kezdesnek diagonalis formak:

- `Q = diag(Q_p, Q_v)`
- `R = diag(R_p, R_v)`

Ha a cel kifejezetten az ar-volumen korrelacio becslese:

- engedelyezheto off-diagonal (`Q_pv`, `R_pv`), de ez parameter- es instabilitas-kockazatot hoz.

---

## 3. Miert lehet erdemes 2D-re valtani

1. **Korrelalt innovaciok kezelese**
   - ha armozgasok tipikusan volumen valtozassal jonnek, a 2D modell kepes ezt explicit kezelni.

2. **Likviditas/aktivitas rezsim becsles**
   - a becsult `v_t` (log-volume) es annak bizonytalansaga (`P_vv`) rezsim-jel lehet.

3. **Koherensebb zajmodell**
   - a volume-t nem csak "szabaly" szerint hasznaljuk, hanem a szuro sajat kovetkezteteset is belevesszuk.

Ellensuly:

- tobb hiperparameter (`Q_v`, `R_v`, esetleg kovarianciak),
- tobb numerikus buktato (2x2 inverzio, skala, outlierek),
- volume meres sajatossagai (heavy-tail, tori az eloszlast, exchange-specifikus zajok).

---

## 4. Hogyan illeszkedik a jelenlegi rendszerbe

### 4.1 Erintett fajlok

- `backend/kalman/engine.py`
- `backend/store.py`
- `backend/config.py`
- `backend/models.py`
- `frontend/src/types/index.ts`
- opcionálisan `frontend/src/components/StatusBar.vue` (ha volume estimate megjelenik)

### 4.2 API es adatmodellek

Jelenleg a frontendnek a `KalmanResult` csak price-savokat es gain-t kuld.

2D-nel ket lehetoseg van:

Opcio A (minimal):

- kimenet marad teljesen ugyanaz, savok csak `P_pp`-bol
- volume becsles belso, nem exportaljuk

Opcio B (debug/feature):

- `KalmanResult` bovitese:
  - `estimated_volume: float`
  - `volume_uncertainty: float` (pl. `P_vv`)
  - `kalman_gain_price: float` (vagy `K[0,0]`), `kalman_gain_volume: float` (vagy `K[1,1]`)

Kezdesnek javasolt: Opcio A vagy nagyon visszafogott debug (csak `estimated_volume`, `P_vv`).

---

## 5. Matematikai lepesek (2D)

Jelolesek:

- `x` 2x1, `P` 2x2
- `F`, `Q`, `H`, `R` 2x2

Predict:

- `x_pred = F x`
- `P_pred = F P F^T + Q`

Update:

- innovacio: `y = z - H x_pred`
- innovacio-kov: `S = H P_pred H^T + R`
- gain: `K = P_pred H^T S^{-1}`
- allapot: `x = x_pred + K y`
- kovariancia: `P = (I - K H) P_pred`

Mivel 2x2, `S^{-1}` zart formaban is inverzalhato (gyors es egyszeru), nem kell altalanos matrix lib.

Savok a price komponensbol:

- `p_est = exp(x[0])`
- `sigma_p = sqrt(P[0,0])`
- `upper_k = exp(x[0] + k * sigma_p)`
- `lower_k = exp(x[0] - k * sigma_p)`

---

## 6. Volumen kezelesi reszletek

### 6.1 Log transzformacio

Javaslat:

- `v_meas = log1p(volume)`

Ok:

- volume heavy-tail -> log stabilizal,
- `log1p` kezeli a 0-t,
- skala-problema csokken.

### 6.2 Outlier es clamp

2D-nel erdemes a volume meresre outlier vedelmet adni, pl.:

- `v_meas = clamp(v_meas, v_min, v_max)`

vagy robust meresi zaj:

- `R_v` ideiglenes novelese, ha `|y_v|` nagy.

Elso iteracioban eleg:

- egyszeru clamp + normal, fix `R_v`.

---

## 7. Implementacios terv ebben a repoban

### 7.1 Config

`backend/config.py` bovitese:

- `Q_P`, `R_P` (price)
- `Q_V`, `R_V` (volume)
- opcionálisan `Q_PV`, `R_PV` (korrelacio, default 0)
- `VOL_EPS` (log1p-hez lehet 0, de ha sima log van, kell eps)

Megjegyzes: a jelenlegi `Q` es `R` price-ra vonatkozik. V2-ben a nevkozoseg miatt tisztazni kell.

### 7.2 Engine

`backend/kalman/engine.py`:

- `KalmanFilter` belso allapot:
  - `x`: 2 elem (price_log, volume_log)
  - `P`: 2x2
- `initialize(first_price, first_volume)`
- `update(timestamp, price, volume)`

Megvalositas szempontjai:

- 2x2 matrix muveletek kezzel (floatokkal), hogy minimalis legyen a fuggoseg.
- `S` inverzio: determinant + swap/negate formula.
- numerikus vedelem: det minimum clamp, illetve `R` mindig pozitiv.

### 7.3 Store

`backend/store.py`:

- `update(candle.timestamp, candle.close, candle.volume)`
- `bulk_load` elso candle-bol init mindkettot.

### 7.4 Model/Frontend

Ha exportaljuk a volume becslest:

- `backend/models.py` `KalmanResult` bovitese
- `frontend/src/types/index.ts` frissitese
- `frontend/src/components/StatusBar.vue` opcionális mezok

Ha nem exportaljuk:

- csak backend engine/store valtozik.

---

## 8. Pseudocode (2x2, F=I, H=I)

```python
# x = [p, v]
p_meas = math.log(price)
v_meas = math.log1p(volume)
z0, z1 = p_meas, v_meas

# Predict (F=I)
x0p, x1p = x0, x1
P00p = P00 + Q00
P01p = P01 + Q01
P10p = P10 + Q10
P11p = P11 + Q11

# S = P_pred + R (H=I)
S00 = P00p + R00
S01 = P01p + R01
S10 = P10p + R10
S11 = P11p + R11

# inv(S)
det = S00 * S11 - S01 * S10
invS00 =  S11 / det
invS01 = -S01 / det
invS10 = -S10 / det
invS11 =  S00 / det

# K = P_pred * inv(S)
K00 = P00p * invS00 + P01p * invS10
K01 = P00p * invS01 + P01p * invS11
K10 = P10p * invS00 + P11p * invS10
K11 = P10p * invS01 + P11p * invS11

# y = z - x_pred
y0 = z0 - x0p
y1 = z1 - x1p

# x = x_pred + K y
x0 = x0p + K00 * y0 + K01 * y1
x1 = x1p + K10 * y0 + K11 * y1

# P = (I - K) * P_pred (H=I)
I00, I11 = 1.0, 1.0
A00 = I00 - K00
A01 =     - K01
A10 =     - K10
A11 = I11 - K11

P00 = A00 * P00p + A01 * P10p
P01 = A00 * P01p + A01 * P11p
P10 = A10 * P00p + A11 * P10p
P11 = A10 * P01p + A11 * P11p
```

---

## 9. Tesztelesi terv

### 9.1 Numerikus helyesseg

- `P` szimmetria kozel (P01 ~ P10)
- `P` pozitiv definitsag/pozitiv foatlo
- `det(S)` nem 0 (vedelem clamp-pel)

### 9.2 Viselkedes

- ha `Q_v` es `R_v` nagyon nagy -> volume gyakorlatilag irrelevans a price-hoz (minimalis atfolyas)
- ha off-diagonal 0 -> price update csak `y0`-t hasznal (K01 ~ 0), stabil baseline
- ha csatolas/kovariancia nem 0 -> ellenorizni, hogy nincs "volumen altal rangatott price" tulzottan

### 9.3 Integracio

- bootstrap + live WS nem torik
- snapshot schema kompatibilitas megmarad (ha nem bovited a modellt)

---

## 10. Parameter tuning guide (V2)

Kezdo javaslat (diagonalis, nincs korrelacio):

- `Q_p`: maradhat a mostani `Q`
- `R_p`: maradhat a mostani `R`
- `Q_v`: kicsi (pl. 1e-4 ... 1e-3 log-volume teren, timeframe-fuggo)
- `R_v`: kozepes/nagy (pl. 1e-2 ... 1e-1), mert a volume meres zajos
- `P0`: 2x2, pl. `diag(P0_p, P0_v)`

Ha korrelaciot akarsz:

- elobb stabilizald diagonalisan,
- utana nagyon kicsi off-diagonal (`Q_pv`, `R_pv`) es figyeld a hatast.

---

## 11. Kockazatok es vedelmek

1. **Volume heavy-tail/outlier**
   - vedekezes: log1p, clamp, vagy adaptiv `R_v` outlier eseten.

2. **Tulparameterezett modell**
   - vedekezes: kezdes diagonalis `Q`/`R`, off-diagonal default 0.

3. **Nem kivant atfolyas a price-ba**
   - vedekezes: maradj `F=I`, `H=I`, off-diagonal 0 az elso korben.

4. **Schema toras a frontend felé**
   - vedekezes: Opcio A (nem exportaljuk a volume becslest) az elso rolloutban.

---

## 12. Rollout strategia

1. **Phase 1**: 2D engine belul, de a publikus `KalmanResult` marad valtozatlan.
2. **Phase 2**: debug mezok exportja (estimated_volume, P_vv) feature flaggel.
3. **Phase 3**: korrelacio/csatolas csak ha Phase 1-2 stabil.

Rollback opcio:

- visszaallitas a jelenlegi 1D engine-re,
- vagy 2D-n belul off-diagonal 0, es a price-komponens parameterei a regiek.

---

## 13. Donto javaslat

Ha a celod elsodlegesen a price becsles javitasa volumen alapjan, a V1 (adaptiv `R_t`) tipikusan jobb ROI.

A 2D (V2) akkor indokolt, ha:

- explicit volume rezsim/likviditas becslest is szeretnel,
- vagy kiserleti jelleggel korrelaciot/atfolyast akarsz tanulni es monitorozni.
