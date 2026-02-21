import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from kalman.engine import KalmanFilter
from store import CandleStore
from models import Candle
from bybit.rest_client import async_fetch_historical_candles
from bybit.ws_client import BybitWsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global state ──────────────────────────────────────────
kalman = KalmanFilter(
    Q=settings.Q,
    R=settings.R,
    P0=settings.P0,
    k_band_1=settings.K_BAND_1,
    k_band_2=settings.K_BAND_2,
    k_band_3=settings.K_BAND_3,
)
store = CandleStore(kalman=kalman, maxlen=settings.CANDLE_STORE_SIZE)
connected_clients: set[WebSocket] = set()
bybit_ws_task: asyncio.Task | None = None


# ── Broadcast helper ──────────────────────────────────────
async def broadcast(data: dict) -> None:
    if not connected_clients:
        return
    payload = json.dumps(data)
    stale: list[WebSocket] = []
    for ws in connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            stale.append(ws)
    for ws in stale:
        connected_clients.discard(ws)


# ── Bybit WS callbacks ───────────────────────────────────
async def on_candle(candle: Candle) -> None:
    result = store.add_candle(candle)
    if result is None:
        return
    await broadcast(
        {
            "type": "candle",
            "candle": candle.model_dump(),
            "kalman": result.model_dump(),
        }
    )


async def on_tick(price: float, timestamp: int) -> None:
    await broadcast({"type": "tick", "price": price, "timestamp": timestamp})


# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global bybit_ws_task

    # 1. Bootstrap historical data
    logger.info(
        "Bootstrapping %d candles for %s ...", settings.BOOTSTRAP_CANDLES, settings.SYMBOL
    )
    candles = await async_fetch_historical_candles(
        symbol=settings.SYMBOL,
        category=settings.CATEGORY,
        interval=settings.INTERVAL,
        limit=settings.BOOTSTRAP_CANDLES,
    )
    store.bulk_load(candles)
    logger.info("Bootstrap complete. Store has %d candles.", len(store.candles))

    # 2. Start Bybit WebSocket
    bybit_ws = BybitWsClient(
        symbol=settings.SYMBOL,
        category=settings.CATEGORY,
        interval=settings.INTERVAL,
        on_candle=on_candle,
        on_tick=on_tick,
    )
    bybit_ws_task = asyncio.create_task(bybit_ws.start())
    logger.info("Bybit WebSocket started.")

    yield

    # Shutdown
    await bybit_ws.stop()
    if bybit_ws_task:
        bybit_ws_task.cancel()
    logger.info("Shutdown complete.")


# ── App ───────────────────────────────────────────────────
app = FastAPI(title="Smart Bollinger Band", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST endpoints ────────────────────────────────────────
@app.get("/api/snapshot")
async def get_snapshot():
    return store.get_snapshot()


@app.get("/api/config")
async def get_config():
    return {
        "symbol": settings.SYMBOL,
        "category": settings.CATEGORY,
        "interval": settings.INTERVAL,
        "Q": settings.Q,
        "R": settings.R,
        "P0": settings.P0,
        "k_band_1": settings.K_BAND_1,
        "k_band_2": settings.K_BAND_2,
        "k_band_3": settings.K_BAND_3,
    }


# ── WebSocket endpoint ───────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info("Frontend WS client connected. Total: %d", len(connected_clients))
    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info("Frontend WS client disconnected. Total: %d", len(connected_clients))
