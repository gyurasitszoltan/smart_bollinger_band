import asyncio
import json
import logging
from typing import Callable, Awaitable

import websockets

from models import Candle

logger = logging.getLogger(__name__)

WS_ENDPOINTS = {
    "linear": "wss://stream.bybit.com/v5/public/linear",
    "spot": "wss://stream.bybit.com/v5/public/spot",
    "inverse": "wss://stream.bybit.com/v5/public/inverse",
}

PING_INTERVAL = 20
INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 60.0

OnCandleCallback = Callable[[Candle], Awaitable[None]]
OnTickCallback = Callable[[float, int], Awaitable[None]]


class BybitWsClient:
    def __init__(
        self,
        symbol: str,
        category: str,
        interval: str,
        on_candle: OnCandleCallback,
        on_tick: OnTickCallback,
    ):
        self.symbol = symbol
        self.category = category
        self.interval = interval
        self.on_candle = on_candle
        self.on_tick = on_tick
        self._running = False

    async def start(self) -> None:
        self._running = True
        backoff = INITIAL_BACKOFF
        endpoint = WS_ENDPOINTS.get(self.category, WS_ENDPOINTS["linear"])
        topic = f"kline.{self.interval}.{self.symbol}"

        while self._running:
            try:
                async with websockets.connect(endpoint) as ws:
                    # Subscribe
                    sub_msg = json.dumps({"op": "subscribe", "args": [topic]})
                    await ws.send(sub_msg)
                    logger.info("Subscribed to %s on %s", topic, endpoint)
                    backoff = INITIAL_BACKOFF

                    # Start ping task
                    ping_task = asyncio.create_task(self._ping_loop(ws))

                    try:
                        async for raw in ws:
                            await self._handle_message(raw)
                    finally:
                        ping_task.cancel()

            except (websockets.ConnectionClosed, OSError) as e:
                if not self._running:
                    break
                logger.warning("Bybit WS disconnected: %s. Reconnecting in %.1fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

    async def stop(self) -> None:
        self._running = False

    async def _ping_loop(self, ws: websockets.ClientConnection) -> None:
        try:
            while True:
                await asyncio.sleep(PING_INTERVAL)
                await ws.send(json.dumps({"op": "ping"}))
        except asyncio.CancelledError:
            pass

    async def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Skip non-kline messages (subscription confirmations, pongs, etc.)
        if "topic" not in msg or "data" not in msg:
            return

        for item in msg["data"]:
            confirm = item.get("confirm", False)

            if confirm:
                candle = Candle(
                    timestamp=int(item["start"]),
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=float(item["volume"]),
                )
                await self.on_candle(candle)
            else:
                price = float(item["close"])
                ts = int(item["timestamp"])
                await self.on_tick(price, ts)
