# Implementacio: Smart Bollinger Band (tenyleges allapot)

Ez a dokumentum a projekt **jelenleg megvalositott** allapotat irja le.
Nem tervezett lepessor, hanem kodszintu allapotjelentes.

---

## 1. Megvalositott funkcionalitas

### 1.1 Backend

- FastAPI alkalmazas fut `backend/main.py` alatt.
- Indulaskor historical bootstrap tortenik Bybit REST-bol.
- A bootstrap gyertyak feldolgozasa utan Bybit live WebSocket indul.
- Lezart gyertya eseten Kalman update + broadcast frontend fele.
- Tick eseten csak ar frissites broadcast megy.
- Elert endpointok:
  - `GET /api/snapshot`
  - `GET /api/config`
  - `WS /ws`

### 1.2 Kalman motor

- 1D random walk Kalman (`backend/kalman/engine.py`).
- Bemenet: `ln(price)` (log-ter), kimenet vissza `exp(...)`.
- Kiszamolt mezok gyertyanal:
  - `estimated_price`
  - `uncertainty`
  - `upper_1/lower_1`
  - `upper_2/lower_2`
  - `upper_3/lower_3`
  - `kalman_gain`

### 1.3 In-memory adattar

- `backend/store.py` `deque`-ket hasznal.
- Gyertya deduplikacio timestamp alapjan tortenik.
- Snapshot response a teljes chart inicializalashoz ad adatot.

### 1.4 Frontend

- Vue 3 + TypeScript + Vite projekt (`frontend/`).
- Snapshot betoltes indulaskor (`/api/snapshot`).
- Sajat WS composable automata reconnecttel.
- Chart: `lightweight-charts` candlestick + 3 savpar + kozepvonal.
- Status bar: kapcsolati status + aktualis Kalman ertekek.

---

## 2. Projektfak es felelossegek

### Backend
- `backend/main.py`: app lifecycle, endpointok, broadcast
- `backend/config.py`: runtime konfiguracio
- `backend/models.py`: Pydantic modellek
- `backend/store.py`: gyertyatar + snapshot
- `backend/kalman/engine.py`: szuroalgoritmus
- `backend/bybit/rest_client.py`: bootstrap REST kliens
- `backend/bybit/ws_client.py`: live WS kliens

### Frontend
- `frontend/src/App.vue`: app orchestration
- `frontend/src/composables/useWebSocket.ts`: WS kapcsolatkezeles
- `frontend/src/components/CandleChart.vue`: chart logika
- `frontend/src/components/StatusBar.vue`: allapotsor
- `frontend/src/types/index.ts`: TS tipusok
- `frontend/vite.config.ts`: proxy beallitasok

---

## 3. Futtatasi folyamat

1. Backend indul.
2. Historical candles letoltes Bybitrol.
3. Store + Kalman inicializalasa/futtatasa bootstrap adatokon.
4. Bybit live WS inditas.
5. Frontend snapshotot ker.
6. Frontend WS-re csatlakozik.
7. Candle/tick broadcastokkal valos ideju chart frissites.

---

## 4. Aktualis konfiguracios defaultok

`backend/config.py` szerint:

- `SYMBOL=BTCUSDT`
- `CATEGORY=linear`
- `INTERVAL=1`
- `BOOTSTRAP_CANDLES=1000`
- `Q=1e-7`
- `R=1e-4`
- `P0=1.0`
- `K_BAND_1=1.0`
- `K_BAND_2=2.0`
- `K_BAND_3=3.0`
- `HOST=0.0.0.0`
- `PORT=8000`
- `CANDLE_STORE_SIZE=800`

---

## 5. Ismert nyitott pontok

- Nincs perzisztens tarolas (restart utan uj bootstrap).
- Nincs runtime config update endpoint (POST/PATCH).
- Nincs backend oldali hianyzo gyertya visszatoltes reconnect utan.
- Nincs automatizalt tesztcsomag commitolva (`tests/` nincs).

---

## 6. MVP statusz

A jelenlegi kod bazis egy mukodo MVP, amely:
- valos ideju adatot fogad,
- Kalman alapu savokat szamol,
- es frontend charton folyamatosan megjelenit.
