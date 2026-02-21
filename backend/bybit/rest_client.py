import asyncio
import logging
import time

from pybit.unified_trading import HTTP

from models import Candle

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


BYBIT_MAX_LIMIT = 1000


def _fetch_one_page(
    session: HTTP,
    symbol: str,
    category: str,
    interval: str,
    limit: int,
    end: int | None = None,
) -> list[Candle]:
    """Fetch a single page of candles with retry logic."""
    last_err: Exception | None = None
    kwargs = dict(category=category, symbol=symbol, interval=interval, limit=limit)
    if end is not None:
        kwargs["end"] = end

    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get_kline(**kwargs)

            if resp["retCode"] != 0:
                raise RuntimeError(f"Bybit API error: {resp['retMsg']}")

            raw_list = resp["result"]["list"]
            raw_list.reverse()  # Bybit returns reverse-chronological → flip

            return [
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


def fetch_historical_candles(
    symbol: str, category: str, interval: str, limit: int
) -> list[Candle]:
    session = HTTP(testnet=False)
    all_candles: list[Candle] = []
    remaining = limit

    end: int | None = None  # first request: latest candles

    while remaining > 0:
        page_size = min(remaining, BYBIT_MAX_LIMIT)
        page = _fetch_one_page(session, symbol, category, interval, page_size, end)

        if not page:
            break

        all_candles = page + all_candles  # prepend (older candles first)
        remaining -= len(page)

        logger.info(
            "Fetched %d candles (total so far: %d / %d) for %s",
            len(page),
            len(all_candles),
            limit,
            symbol,
        )

        if len(page) < page_size:
            break  # no more data available

        # Next page: end just before the oldest candle we got
        end = page[0].timestamp - 1

    logger.info(
        "Fetched %d historical candles for %s (%s, %sm)",
        len(all_candles),
        symbol,
        category,
        interval,
    )
    return all_candles


async def async_fetch_historical_candles(
    symbol: str, category: str, interval: str, limit: int
) -> list[Candle]:
    """Async wrapper — runs the sync pybit call in a thread pool."""
    return await asyncio.to_thread(
        fetch_historical_candles, symbol, category, interval, limit
    )
