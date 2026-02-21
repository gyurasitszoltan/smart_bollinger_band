# Rendszerterv: Smart Bollinger Band (aktualis allapot)

## 1. Attekintes

A projekt egy valos ideju kriptoindikator rendszer, amely Bybit gyertyaadatokbol
Kalman-szuro alapjan szamol dinamikus savokat, majd ezt Vue frontendben rajzolja ki.

Fobb cel:
- gyorsan frissulo becsult kozepvonal,
- a bizonytalansagbol kepzett 3 savpar (B1/B2/B3),
- egyszeru snapshot + WebSocket adatkuldes frontend fele.

--- 

## 2. Architektura

```text
Bybit REST (bootstrap)               Bybit WebSocket (kline stream)
        |                                         |
        v                                         v
   +---------------------------------------------------------+
   |                   Backend (FastAPI)                     |
   |                                                         |
   |  bybit/rest_client.py -> CandleStore -> KalmanFilter   |
   |                                  |                      |
   |                                  +-> GET /api/snapshot  |
   |                                  +-> GET /api/config    |
   |                                  +-> WS /ws broadcast   |
   +-------------------------------+-------------------------+
                                   |
                                   v
                       Frontend (Vue 3 + lightweight-charts)
                       - Snapshot letoltes
                       - WS kapcsolat
                       - Candlestick + Kalman savok
```

---

## 3. Backend terv (megvalositott)

### 3.1 Konfiguracio
`backend/config.py` (`BaseSettings`):
- Piaci parameterek: `SYMBOL`, `CATEGORY`, `INTERVAL`, `BOOTSTRAP_CANDLES`
- Kalman parameterek: `Q`, `R`, `P0`, `K_BAND_1`, `K_BAND_2`, `K_BAND_3`
- Szerver/store: `HOST`, `PORT`, `CANDLE_STORE_SIZE`

### 3.2 Adatmodellek
`backend/models.py`:
- `Candle`
- `KalmanResult`
- `SnapshotResponse`

### 3.3 Kalman motor
`backend/kalman/engine.py`:
- 1D random walk Kalman,
- belso allapot log-ar terben (`x = ln(price)`),
- kimenet visszakonvertalva ar-terbe (`exp(x)`),
- 3 savpar ugyanabbal a `sqrt(P)` ertekkel.

Szamitas lezart gyertyanal:
1. `z = ln(close)`
2. `x_pred = x`, `P_pred = P + Q`
3. `K = P_pred / (P_pred + R)`
4. `x = x_pred + K * (z - x_pred)`
5. `P = (1 - K) * P_pred`
6. `estimated`, `upper_1/lower_1`, `upper_2/lower_2`, `upper_3/lower_3`

### 3.4 In-memory store
`backend/store.py`:
- `deque` alapú gyertyatar + Kalman kimenetek,
- deduplikacio timestamp alapjan (`<= last_timestamp` skip),
- snapshot eloallitas frontend inicializalashoz.

### 3.5 Bybit adatforrasok

`backend/bybit/rest_client.py`:
- bootstrap hisztorikus adatok letoltese,
- retry (3 probalkozas) exponencialis varakozassal,
- reverse kronologia rendezese idorendbe.

`backend/bybit/ws_client.py`:
- public endpoint category szerint,
- subscribe: `kline.{interval}.{symbol}`,
- ping 20 mp-enkent,
- reconnect exponencialis backoff-fal,
- `confirm=true`: lezart gyertya callback,
- `confirm=false`: tick callback.

### 3.6 FastAPI app
`backend/main.py`:
- lifespan indulaskor:
  1) REST bootstrap,
  2) `store.bulk_load`,
  3) Bybit WS task inditas,
- endpointok:
  - `GET /api/snapshot`
  - `GET /api/config`
  - `WS /ws`
- frontend klienseknek broadcast JSON.

---

## 4. Frontend terv (megvalositott)

### 4.1 App szint
`frontend/src/App.vue`:
- indulaskor snapshot letoltes,
- majd WS kapcsolat,
- allapot tovabbadas `StatusBar` es `CandleChart` fele.

### 4.2 WS composable
`frontend/src/composables/useWebSocket.ts`:
- status kezeles (`connecting`, `connected`, `disconnected`),
- utolso uzenet parse,
- automatikus reconnect 3 masodpercenkent.

### 4.3 Chart komponens
`frontend/src/components/CandleChart.vue`:
- TradingView `lightweight-charts`,
- 1 candlestick sorozat,
- 1 kozepvonal + 3 savpar (6 line),
- tick eseten utolso gyertya elo frissitese,
- ablakatmeretezes kezelese.

### 4.4 StatusBar
`frontend/src/components/StatusBar.vue`:
- kapcsolat allapot,
- symbol/interval,
- utolso becsles, savok, gain, bizonytalansag.

### 4.5 Vite proxy
`frontend/vite.config.ts`:
- `/api` -> `http://localhost:8000`
- `/ws` -> `ws://localhost:8000`

---

## 5. Adatfolyam

### 5.1 Indulas
1. Backend indul.
2. REST bootstrap (`BOOTSTRAP_CANDLES`) Bybitrol.
3. Store + Kalman feltoltes.
4. Bybit WS kapcsolat inditasa.
5. Frontend snapshotot ker.
6. Frontend WS-re csatlakozik.

### 5.2 Elo frissites
1. Bybit WS uzenet erkezik.
2. Lezart gyertya (`confirm=true`):
   - store update,
   - Kalman update,
   - broadcast `{ type: "candle", candle, kalman }`.
3. Nyitott gyertya (`confirm=false`):
   - broadcast `{ type: "tick", price, timestamp }`.
4. Frontend chart valos idoben frissul.

---

## 6. Ismert korlatok

- Nincs perzisztens adatbazis, minden memoriaban van.
- Ujrainditas utan allapot ujra bootstrapbol epul.
- Nincs futasideju config update endpoint (jelenleg csak GET config van).
- Symbol/category/interval valtas restarttal tortenik.

---

## 7. Konyvtarak

Backend:
- `fastapi`, `uvicorn[standard]`, `pybit`, `numpy`, `websockets`

Frontend:
- `vue`, `lightweight-charts`, `vite`, `typescript`

---

## 8. Osszefoglalo

A rendszer jelenleg mukodo MVP:
- bootstrap + live Bybit adatfolyam,
- log-teres Kalman becsles,
- 3 savparos vizualizacio,
- snapshot API es frontend WebSocket frissites.
