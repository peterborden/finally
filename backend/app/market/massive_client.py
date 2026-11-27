"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import logging
import time

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource
from .utils import normalize_ticker

logger = logging.getLogger(__name__)

# Massive/Polygon trade timestamps are Unix nanoseconds.
NANOSECONDS_PER_SECOND = 1_000_000_000


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min → poll every 15s (default)
      - Paid tiers: higher limits → poll every 2-5s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = [normalize_ticker(t) for t in tickers]

        # Do an immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(tickers),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = normalize_ticker(ticker)
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s", ticker)
            # Poll immediately so the new ticker has a price right away rather
            # than waiting up to poll_interval seconds for the next cycle.
            if self._client:
                await self._poll_once()

    async def remove_ticker(self, ticker: str) -> None:
        ticker = normalize_ticker(ticker)
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- Internal ---

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch snapshots, update cache."""
        if not self._tickers or not self._client:
            return

        try:
            # The Massive RESTClient is synchronous — run in a thread to
            # avoid blocking the event loop.
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    last_trade = snap.last_trade
                    price = last_trade.price
                    if price is None:
                        raise ValueError("missing last trade price")
                    self._cache.update(
                        ticker=snap.ticker,
                        price=price,
                        timestamp=self._trade_timestamp(last_trade),
                        # Prior-day close is the natural daily-change reference.
                        reference_price=self._reference_price(snap),
                    )
                    processed += 1
                except (AttributeError, TypeError, ValueError) as e:
                    logger.warning(
                        "Skipping snapshot for %s: %s",
                        getattr(snap, "ticker", "???"),
                        e,
                    )
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise — the loop will retry on the next interval.
            # Common failures: 401 (bad key), 429 (rate limit), network errors.

    @staticmethod
    def _trade_timestamp(last_trade) -> float:
        """Best-available trade timestamp, in Unix seconds.

        Massive's LastTrade exposes nanosecond timestamps under several names
        (sip/participant/trf); the legacy `.timestamp` attribute does not exist.
        Falls back to wall-clock time when none are present so a valid price is
        never discarded over a missing timestamp.
        """
        ts_ns = (
            getattr(last_trade, "sip_timestamp", None)
            or getattr(last_trade, "participant_timestamp", None)
            or getattr(last_trade, "trf_timestamp", None)
        )
        if ts_ns is None:
            return time.time()
        return ts_ns / NANOSECONDS_PER_SECOND

    @staticmethod
    def _reference_price(snap) -> float | None:
        """Prior-day close for daily-change calculations, or None if absent."""
        prev_day = getattr(snap, "prev_day", None)
        close = getattr(prev_day, "close", None) if prev_day is not None else None
        return close if close else None

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API. Runs in a thread."""
        # NOTE: pass the enum's .value ("stocks"), not the enum itself. The massive
        # SDK interpolates market_type directly into the URL path, and this plain
        # Enum stringifies to "SnapshotMarketType.STOCKS" -> malformed path -> 404.
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS.value,
            tickers=self._tickers,
        )
