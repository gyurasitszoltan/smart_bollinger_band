# Smart Bollinger Band - Kezikonyv (aktualis verzio)

Ez az utmutato a jelenlegi kodallapothoz tartozik.

---

## 1. Gyors inditas

### 1.1 Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Ha hibat kapsz erre: `ModuleNotFoundError: pydantic_settings`, telepitsd:

```bash
pip install pydantic-settings
```

### 1.2 Frontend

```bash
cd frontend
npm install
npm run dev
```

Nyisd meg: `http://localhost:5173`

---

## 2. Mit csinal a rendszer?

- Bybitrol letolti az indulashoz szukseges historical gyertyakat.
- Ezeken lefuttatja a log-ar terben mukodo Kalman szurot.
- Elinditja a live Bybit WebSocketet.
- A frontendnek snapshotot ad (`/api/snapshot`) es WS-en pusholja a frissiteseket (`/ws`).
- A frontend candlestick charton mutatja:
  - becsult kozepvonal,
  - 3 savpar (B1/B2/B3),
  - kapcsolat/allapot informaciok.

---

## 3. Konfiguracio

A beallitasok a `backend/config.py` fajlban vannak, `BaseSettings` alapon.
Ertekadas sorrend:
1. Kornyezeti valtozo
2. `.env` fajl (ha hasznalsz ilyet)
3. Kodbeli default

Peldak:

```bash
set SYMBOL=ETHUSDT
set INTERVAL=5
set Q=1e-6
set R=1e-4
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 4. Parameterek referencia

| Parameter | Tipus | Default | Leiras |
|---|---|---|---|
| `SYMBOL` | str | `BTCUSDT` | Bybit instrumentum |
| `CATEGORY` | str | `linear` | Piac tipus (`linear`, `spot`, `inverse`) |
| `INTERVAL` | str | `1` | Gyertya periodus |
| `BOOTSTRAP_CANDLES` | int | `1000` | Indulaskori historical gyertyak |
| `Q` | float | `1e-7` | Folyamatzaj log-terben |
| `R` | float | `1e-4` | Meresi zaj log-terben |
| `P0` | float | `1.0` | Kezdeti bizonytalansag |
| `K_BAND_1` | float | `1.0` | Belso sav szorzo |
| `K_BAND_2` | float | `2.0` | Kozepso sav szorzo |
| `K_BAND_3` | float | `3.0` | Kulso sav szorzo |
| `HOST` | str | `0.0.0.0` | Szerver bind cim |
| `PORT` | int | `8000` | Szerver port |
| `CANDLE_STORE_SIZE` | int | `800` | In-memory store meret |

---

## 5. Kalman modell roviden

A backendben egy 1D random walk Kalman fut (`backend/kalman/engine.py`).
Minden lezart gyertyanal:

1. `z = ln(close)`
2. Predikcio: `x_pred = x`, `P_pred = P + Q`
3. Gain: `K = P_pred / (P_pred + R)`
4. Frissites:
   - `x = x_pred + K * (z - x_pred)`
   - `P = (1 - K) * P_pred`
5. Kimenet ar-terbe: `estimated_price = exp(x)`
6. Savok:
   - `upper_n = exp(x + K_BAND_n * sqrt(P))`
   - `lower_n = exp(x - K_BAND_n * sqrt(P))`

Ezert a savok multiplikativak, nem fix dollar tavolsaguak.

---

## 6. API es WS

### 6.1 `GET /api/snapshot`
Visszaadja:
- gyertyak listaja,
- Kalman eredmenyek listaja,
- symbol/interval,
- aktualis Q/R es savszorzok.

### 6.2 `GET /api/config`
Visszaadja a futo backend konfiguraciojat.

### 6.3 `WS /ws`
Uzenetek:

```json
{
  "type": "candle",
  "candle": {"timestamp": 0, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0},
  "kalman": {
    "timestamp": 0,
    "estimated_price": 0,
    "uncertainty": 0,
    "upper_1": 0,
    "lower_1": 0,
    "upper_2": 0,
    "lower_2": 0,
    "upper_3": 0,
    "lower_3": 0,
    "kalman_gain": 0
  }
}
```

```json
{
  "type": "tick",
  "price": 0,
  "timestamp": 0
}
```

---

## 7. Hibaelharitas

- Backend nem indul:
  - ellenorizd a Python verziot,
  - telepitsd a fuggosegeket,
  - ha kell: `pip install pydantic-settings`.

- Frontend nem eri el az API-t:
  - fut-e backend a 8000-es porton,
  - egyezik-e `frontend/vite.config.ts` proxy celcime.

- Nincs elo adat a charton:
  - nezd meg a backend logot (Bybit WS kapcsolat),
  - ellenorizd a `SYMBOL`, `CATEGORY`, `INTERVAL` beallitasokat.

---

## 8. Fontos korlatok

- A tarolas in-memory, restart utan nincs lokalis historikus allapot.
- Konfiguracio modositasa futas kozben nem tamogatott API-n keresztul.
- Symbol valtas jelenleg restartot igenyel.

---

## 9. Fajlok gyors terkep

- Backend belepesi pont: `backend/main.py`
- Kalman motor: `backend/kalman/engine.py`
- Store: `backend/store.py`
- Bybit REST/WS: `backend/bybit/rest_client.py`, `backend/bybit/ws_client.py`
- Frontend app: `frontend/src/App.vue`
- Chart: `frontend/src/components/CandleChart.vue`
- Status: `frontend/src/components/StatusBar.vue`

---

Utolso frissites: 2026-02-21
