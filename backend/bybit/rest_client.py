import asyncio
import logging
import time

from pybit.unified_trading import HTTP

from models import Candle

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


def fetch_historical_candles(
    symbol: str, category: str, interval: str, limit: int
) -> list[Candle]:
    session = HTTP(testnet=False)
    last_err: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get_kline(
                category=category,
                symbol=symbol,
                interval=interval,
                limit=limit,
            )

            if resp["retCode"] != 0:
                raise RuntimeError(f"Bybit API error: {resp['retMsg']}")

            raw_list = resp["result"]["list"]
            # Bybit returns reverse-chronological order → reverse to chronological
            raw_list.reverse()

            candles = [
                Candle(
                    timestamp=int(item[0]),
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                )
                for item in raw_list
            ]

            logger.info(
                "Fetched %d historical candles for %s (%s, %sm)",
                len(candles),
                symbol,
                category,
                interval,
            )
            return candles

        except Exception as e:
            last_err = e
            wait = INITIAL_BACKOFF * (2**attempt)
            logger.warning(
                "Bybit REST attempt %d/%d failed: %s. Retrying in %.1fs",
                attempt + 1,
                MAX_RETRIES,
                e,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Failed to fetch historical candles after {MAX_RETRIES} attempts: {last_err}"
    )


async def async_fetch_historical_candles(
    symbol: str, category: str, interval: str, limit: int
) -> list[Candle]:
    """Async wrapper — runs the sync pybit call in a thread pool."""
    return await asyncio.to_thread(
        fetch_historical_candles, symbol, category, interval, limit
    )
