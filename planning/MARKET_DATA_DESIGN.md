# Market Data Backend — Design Document

Implementation guide for the FinAlly market data subsystem. All code shown
here reflects the actual files in `backend/app/market/`.

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [File Structure](#2-file-structure)
3. [Data Model — `models.py`](#3-data-model)
4. [Price Cache — `cache.py`](#4-price-cache)
5. [Abstract Interface — `interface.py`](#5-abstract-interface)
6. [Seed Data — `seed_prices.py`](#6-seed-data)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator)
8. [Massive API Client — `massive_client.py`](#8-massive-api-client)
9. [Factory — `factory.py`](#9-factory)
10. [SSE Streaming — `stream.py`](#10-sse-streaming)
11. [FastAPI Lifecycle Integration](#11-fastapi-lifecycle-integration)
12. [Watchlist Coordination](#12-watchlist-coordination)
13. [Testing](#13-testing)
14. [Error Handling](#14-error-handling)
15. [Configuration Reference](#15-configuration-reference)

---

## 1. Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  — GBM simulator (default; no API key needed)
└── MassiveDataSource    — Polygon.io REST poller (set MASSIVE_API_KEY)
          │
          ▼ writes every ~500ms (sim) or ~15s (Massive)
     PriceCache   (thread-safe, in-memory, version-stamped)
          │
          ├──▶ GET /api/stream/prices  (SSE, reads every 500ms)
          ├──▶ POST /api/portfolio/trade  (reads current price)
          └──▶ GET /api/portfolio  (portfolio valuation)
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **Strategy pattern** | Both sources implement the same ABC. All downstream code is source-agnostic. |
| **Push into shared cache** | Producers write on their own schedule; consumers read independently. No coupling between update cadence and read cadence. |
| **Version counter on cache** | SSE endpoint skips sending when nothing changed — critical when Massive only polls every 15 s. |
| **`threading.Lock` not `asyncio.Lock`** | Massive's synchronous `RESTClient` runs in `asyncio.to_thread()` (a real OS thread). `asyncio.Lock` would not protect against that. |
| **SSE over WebSockets** | One-way server push is all we need; simpler, universally supported, no bidirectional complexity. |
| **Immediate cache seeding** | Both sources seed the cache before the background loop starts, so the first SSE tick has data. |

---

## 2. File Structure

```
backend/
  app/
    market/
      __init__.py        # Public re-exports
      models.py          # PriceUpdate dataclass
      cache.py           # PriceCache — thread-safe in-memory store
      interface.py       # MarketDataSource ABC
      seed_prices.py     # SEED_PRICES, TICKER_PARAMS, correlation constants
      simulator.py       # GBMSimulator + SimulatorDataSource
      massive_client.py  # MassiveDataSource
      factory.py         # create_market_data_source()
      stream.py          # FastAPI SSE router
  tests/
    market/
      test_models.py
      test_cache.py
      test_simulator.py
      test_simulator_source.py
      test_factory.py
      test_massive.py
```

---

## 3. Data Model

**`backend/app/market/models.py`**

`PriceUpdate` is the only type that leaves the market data layer. Everything
downstream — SSE, portfolio valuation, trade execution — works with this.

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

`frozen=True` — immutable value object, safe to share across tasks.  
`slots=True` — small memory savings; many of these are created per second.  
Computed properties (`change`, `direction`, `change_percent`) are derived on
demand so they can never become stale relative to `price`/`previous_price`.

---

## 4. Price Cache

**`backend/app/market/cache.py`**

Central data hub. Sources write; SSE and API routes read. The version counter
lets the SSE endpoint cheaply detect "has anything changed since last send?"

```python
from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price per ticker."""

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price. Returns the PriceUpdate that was stored.

        First update for a ticker: previous_price == price, direction == 'flat'.
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Shallow copy of all current prices."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

### Version counter pattern (used in the SSE loop)

```python
last_version = -1
while True:
    if price_cache.version != last_version:
        last_version = price_cache.version
        yield format_sse(price_cache.get_all())  # only when something changed
    await asyncio.sleep(0.5)
```

With Massive at 15 s poll intervals, the SSE loop calls `get_all()` and
transmits only twice (once per poll), rather than 30 times.

---

## 5. Abstract Interface

**`backend/app/market/interface.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push updates into a shared PriceCache. Downstream
    code never calls the source directly — it reads from the cache.

    Typical lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        await source.add_ticker("TSLA")      # live watchlist changes
        await source.remove_ticker("GOOGL")
        await source.stop()                  # on app shutdown
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates. Call exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker and clear it from the cache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of tracked tickers."""
```

---

## 6. Seed Data

**`backend/app/market/seed_prices.py`**

Constants only. Imported by the simulator for starting prices and GBM
parameters. No logic, no imports.

```python
"""Seed prices and per-ticker parameters for the market simulator."""

SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  420.00,
    "AMZN":  185.00,
    "TSLA":  250.00,
    "NVDA":  800.00,
    "META":  500.00,
    "JPM":   195.00,
    "V":     280.00,
    "NFLX":  600.00,
}

# sigma = annualized volatility, mu = annualized drift
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # high volatility
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # high vol + strong drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},   # low vol (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},   # low vol (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR    = 0.6   # same tech sector
INTRA_FINANCE_CORR = 0.5   # same finance sector
CROSS_GROUP_CORR   = 0.3   # cross-sector and unknown tickers
TSLA_CORR          = 0.3   # TSLA is in the tech group but does its own thing
```

---

## 7. GBM Simulator

**`backend/app/market/simulator.py`**

Two classes in one file: `GBMSimulator` (pure math engine) and
`SimulatorDataSource` (the `MarketDataSource` wrapper).

### 7.1 The math

Geometric Brownian Motion step formula:

```
S(t+dt) = S(t) × exp( (μ − σ²/2)·dt  +  σ·√dt·Z )
```

| Symbol | Meaning |
|---|---|
| `S(t)` | current price |
| `μ` (mu) | annualized drift (expected return) |
| `σ` (sigma) | annualized volatility |
| `dt` | time step as fraction of a trading year |
| `Z` | standard normal random variable, correlated across tickers |

For 500 ms ticks over 252 trading days × 6.5 h/day:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick that accumulate naturally.
Prices can never go negative because `exp()` is always positive.

### 7.2 Correlated moves via Cholesky decomposition

Real stocks do not move independently. The Cholesky decomposition of a
correlation matrix produces a lower-triangular `L` such that `L @ L.T = C`.
Multiplying `L` by a vector of independent normals yields correlated normals:

```python
z_independent = np.random.standard_normal(n)   # n independent draws
z_correlated  = L @ z_independent              # now correlated
```

Correlation structure:
- Same tech sector (AAPL/GOOGL/MSFT/AMZN/META/NVDA/NFLX): **0.6**
- Same finance sector (JPM/V): **0.5**
- TSLA with anything: **0.3** (it does its own thing)
- Cross-sector or unknown: **0.3**

### 7.3 `GBMSimulator` — the math engine

```python
import math, random, logging
import numpy as np
from .seed_prices import (
    CORRELATION_GROUPS, CROSS_GROUP_CORR, DEFAULT_PARAMS,
    INTRA_FINANCE_CORR, INTRA_TECH_CORR, SEED_PRICES, TICKER_PARAMS, TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)   # batch — no Cholesky rebuild yet
        self._rebuild_cholesky()                # single rebuild at the end

    def step(self) -> dict[str, float]:
        """Advance all prices one tick. Returns {ticker: new_price}."""
        n = len(self._tickers)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z_correlated  = self._cholesky @ z_independent if self._cholesky is not None \
                         else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            mu, sigma = self._params[ticker]["mu"], self._params[ticker]["sigma"]

            drift     = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # ~0.1% chance of a random 2-5% shock per tick per ticker
            # With 10 tickers at 2 ticks/s → ~1 event every 50 s
            if random.random() < self._event_prob:
                magnitude = random.uniform(0.02, 0.05)
                sign      = random.choice([-1, 1])
                self._prices[ticker] *= 1 + magnitude * sign
                logger.debug("Random event on %s: %.1f%%", ticker, magnitude * sign * 100)

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # ── internals ──────────────────────────────────────────────────────────

    def _add_ticker_internal(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech    = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]

        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 7.4 `SimulatorDataSource` — async wrapper

```python
import asyncio
from .cache import PriceCache
from .interface import MarketDataSource

class SimulatorDataSource(MarketDataSource):

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache      = price_cache
        self._interval   = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None  = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)

        # Seed cache BEFORE the loop starts — frontend gets data on first SSE tick
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    for ticker, price in self._sim.step().items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

---

## 8. Massive API Client

**`backend/app/market/massive_client.py`**

Polls the Massive (Polygon.io) REST snapshot endpoint on a configurable
interval. The synchronous `RESTClient` is run in `asyncio.to_thread()` to
avoid blocking the event loop.

### Massive API quick reference

```
Package: massive  (pip install -U massive)
Auth:    Authorization: Bearer <API_KEY>  (client handles automatically)

Primary endpoint: GET /v2/snapshot/locale/us/markets/stocks/tickers
                  ?tickers=AAPL,GOOGL,MSFT
```

All tickers fetched in **one API call** — essential for staying inside the
free-tier limit of 5 requests/minute.

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="...")   # or reads MASSIVE_API_KEY from env

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT"],
)

for snap in snapshots:
    print(snap.ticker)                             # "AAPL"
    print(snap.last_trade.price)                   # 190.50
    print(snap.last_trade.timestamp)               # Unix ms  → /1000 for seconds
    print(snap.day.previous_close)                 # prev session close
    print(snap.day.change_percent)                 # day % change
```

### Rate limits

| Tier | Limit | Recommended interval |
|------|-------|----------------------|
| Free | 5 req/min | 15 s (default) |
| Paid | Unlimited | 2–5 s |

### `MassiveDataSource` implementation

```python
from __future__ import annotations

import asyncio
import logging

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """REST-polling data source backed by the Massive (Polygon.io) API."""

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key   = api_key
        self._cache     = price_cache
        self._interval  = poll_interval
        self._tickers: list[str]            = []
        self._task:    asyncio.Task | None  = None
        self._client:  RESTClient | None    = None

    async def start(self, tickers: list[str]) -> None:
        self._client  = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)

        await self._poll_once()   # immediate first poll — cache populated before SSE loop

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info("Massive poller started: %d tickers, %.1fs interval",
                    len(tickers), self._interval)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task   = None
        self._client = None

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # ── internals ──────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """First poll happened in start(). This loop handles subsequent polls."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            # RESTClient is synchronous — offload to a thread pool
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    price     = snap.last_trade.price
                    timestamp = snap.last_trade.timestamp / 1000.0   # ms → s
                    self._cache.update(ticker=snap.ticker, price=price, timestamp=timestamp)
                    processed += 1
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s",
                                   getattr(snap, "ticker", "?"), e)
            logger.debug("Massive poll: %d/%d tickers updated", processed, len(self._tickers))
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise — the loop retries automatically on the next interval

    def _fetch_snapshots(self) -> list:
        """Synchronous Massive API call. Called via asyncio.to_thread."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

### Error handling table

| Error | Behaviour |
|-------|-----------|
| 401 Unauthorized | Logged as error. Loop keeps running (fix key and restart). |
| 429 Rate Limited | Logged as error. Retries after `poll_interval` seconds. |
| Network timeout | Logged as error. Retries on the next interval. |
| Malformed snapshot | Individual ticker skipped with a warning; others still processed. |
| All tickers fail | Cache retains last-known prices; SSE keeps streaming stale-but-non-empty data. |

---

## 9. Factory

**`backend/app/market/factory.py`**

```python
from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Select simulator or Massive based on MASSIVE_API_KEY env var.

    Returns an unstarted source — caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

Note that `massive` is imported at the top of `massive_client.py`, so the
package must be installed even for the simulator path. It is declared as a
core dependency in `pyproject.toml`.

---

## 10. SSE Streaming

**`backend/app/market/stream.py`**

A long-lived HTTP connection that pushes price updates to the browser.
The browser connects with the native `EventSource` API and handles
reconnection automatically via the `retry:` directive.

```python
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Register the /prices route on the module-level router and return it."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",   # disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Yields SSE events; stops on client disconnect."""
    yield "retry: 1000\n\n"   # browser reconnects after 1 s on drop

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()
                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

### Wire format

One SSE event looks like this on the wire:

```
data: {"AAPL":{"ticker":"AAPL","price":190.50,"previous_price":190.42,"timestamp":1707580800.5,"change":0.08,"change_percent":0.042,"direction":"up"},"GOOGL":{...}}

```

(The blank line terminates the event. The browser's `EventSource` fires
`onmessage` for each one.)

### Frontend connection

```typescript
const es = new EventSource('/api/stream/prices');

es.onopen  = () => setStatus('connected');
es.onerror = () => setStatus('reconnecting');   // EventSource retries automatically

es.onmessage = (event) => {
    const prices: Record<string, PriceUpdate> = JSON.parse(event.data);
    // e.g. prices["AAPL"] = { ticker, price, previous_price, change, change_percent, direction, timestamp }
    updateWatchlistPrices(prices);
    appendSparklinePoints(prices);
};
```

---

## 11. FastAPI Lifecycle Integration

**`backend/app/main.py`** — relevant excerpt

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends

from app.market import PriceCache, MarketDataSource, create_market_data_source, create_stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ────────────────────────────────────────────────────────────
    price_cache = PriceCache()
    app.state.price_cache = price_cache

    source = create_market_data_source(price_cache)
    app.state.market_source = source

    initial_tickers = await db.get_watchlist_tickers()   # read from SQLite
    await source.start(initial_tickers)

    app.include_router(create_stream_router(price_cache))

    yield   # ── app running ────────────────────────────────────────────────

    # ── SHUTDOWN ───────────────────────────────────────────────────────────
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


# ── Dependency helpers for route handlers ──────────────────────────────────

def get_price_cache() -> PriceCache:
    return app.state.price_cache

def get_market_source() -> MarketDataSource:
    return app.state.market_source
```

### Using market data in other routes

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api")


@router.post("/portfolio/trade")
async def execute_trade(
    trade: TradeRequest,
    price_cache: PriceCache = Depends(get_price_cache),
):
    price = price_cache.get_price(trade.ticker)
    if price is None:
        raise HTTPException(400, f"No price available for {trade.ticker}. Try again shortly.")
    # ... fill at `price` ...


@router.get("/watchlist")
async def get_watchlist(
    price_cache: PriceCache = Depends(get_price_cache),
):
    rows = await db.get_watchlist()
    return [
        {"ticker": row.ticker, "price": price_cache.get_price(row.ticker)}
        for row in rows
    ]
```

---

## 12. Watchlist Coordination

When the user adds or removes a ticker (via REST or LLM chat), the market
data source must be notified so it tracks the right set.

### Add flow

```
POST /api/watchlist  { "ticker": "PYPL" }
  → INSERT into watchlist table
  → await source.add_ticker("PYPL")
       Simulator: adds to GBMSimulator, rebuilds Cholesky, seeds cache immediately
       Massive:   appends to ticker list; price appears on the next poll (≤ 15 s)
  → return { ticker, price }   (price may be None if Massive hasn't polled yet)
```

### Remove flow

```
DELETE /api/watchlist/PYPL
  → DELETE from watchlist table
  → check for open position (see below)
  → await source.remove_ticker("PYPL")   (only if no open position)
       Both: removes from ticker list and clears PriceCache entry
  → return { status: "ok" }
```

### Edge case — ticker with an open position

```python
@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, ...):
    await db.delete_watchlist(ticker)

    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)   # stop tracking only when flat
    # else: keep streaming prices for portfolio valuation

    return {"status": "ok"}
```

---

## 13. Testing

### 13.1 PriceCache

```python
# backend/tests/market/test_cache.py
from app.market.cache import PriceCache


class TestPriceCache:

    def test_update_and_get(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.ticker == "AAPL"
        assert update.price  == 190.50
        assert cache.get("AAPL") == update

    def test_first_update_is_flat(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.direction      == "flat"
        assert update.previous_price == 190.50

    def test_direction_up(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        assert cache.update("AAPL", 191.00).direction == "up"

    def test_direction_down(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        assert cache.update("AAPL", 189.00).direction == "down"

    def test_remove(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None

    def test_get_all_is_shallow_copy(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        snapshot = cache.get_all()
        del snapshot["AAPL"]
        assert cache.get("AAPL") is not None   # original unaffected

    def test_version_increments(self):
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        assert cache.version == v0 + 1
        cache.update("AAPL", 191.00)
        assert cache.version == v0 + 2

    def test_get_price_convenience(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        assert cache.get_price("AAPL")  == 190.50
        assert cache.get_price("NOPE")  is None
```

### 13.2 GBMSimulator

```python
# backend/tests/market/test_simulator.py
from app.market.simulator import GBMSimulator
from app.market.seed_prices import SEED_PRICES


class TestGBMSimulator:

    def test_step_returns_all_tickers(self):
        sim = GBMSimulator(["AAPL", "GOOGL"])
        assert set(sim.step()) == {"AAPL", "GOOGL"}

    def test_prices_always_positive(self):
        sim = GBMSimulator(["AAPL"])
        for _ in range(10_000):
            assert sim.step()["AAPL"] > 0

    def test_initial_price_matches_seed(self):
        sim = GBMSimulator(["AAPL"])
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_add_ticker(self):
        sim = GBMSimulator(["AAPL"])
        sim.add_ticker("TSLA")
        assert "TSLA" in sim.step()

    def test_remove_ticker(self):
        sim = GBMSimulator(["AAPL", "GOOGL"])
        sim.remove_ticker("GOOGL")
        result = sim.step()
        assert "GOOGL" not in result
        assert "AAPL"  in result

    def test_add_duplicate_is_noop(self):
        sim = GBMSimulator(["AAPL"])
        sim.add_ticker("AAPL")
        assert sim.get_tickers().count("AAPL") == 1

    def test_remove_nonexistent_is_noop(self):
        sim = GBMSimulator(["AAPL"])
        sim.remove_ticker("ZZZZ")   # must not raise

    def test_unknown_ticker_random_seed(self):
        sim = GBMSimulator(["ZZZZ"])
        assert 50.0 <= sim.get_price("ZZZZ") <= 300.0

    def test_empty_step(self):
        assert GBMSimulator([]).step() == {}

    def test_cholesky_none_for_one_ticker(self):
        sim = GBMSimulator(["AAPL"])
        assert sim._cholesky is None

    def test_cholesky_built_for_two_tickers(self):
        sim = GBMSimulator(["AAPL", "GOOGL"])
        assert sim._cholesky is not None

    def test_all_ten_default_tickers(self):
        """Cholesky decomposition must succeed for the full default watchlist."""
        sim = GBMSimulator(list(SEED_PRICES.keys()))
        assert sim._cholesky is not None
        result = sim.step()
        assert len(result) == 10
```

### 13.3 SimulatorDataSource (async integration)

```python
# backend/tests/market/test_simulator_source.py
import asyncio
import pytest
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


@pytest.mark.asyncio
class TestSimulatorDataSource:

    async def test_start_seeds_cache_immediately(self):
        cache  = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])
        assert cache.get("AAPL")  is not None
        assert cache.get("GOOGL") is not None
        await source.stop()

    async def test_version_advances_over_time(self):
        cache  = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])
        v0 = cache.version
        await asyncio.sleep(0.3)
        assert cache.version > v0
        await source.stop()

    async def test_stop_is_idempotent(self):
        cache  = PriceCache()
        source = SimulatorDataSource(price_cache=cache)
        await source.start(["AAPL"])
        await source.stop()
        await source.stop()   # must not raise

    async def test_add_ticker_seeds_cache(self):
        cache  = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])
        await source.add_ticker("TSLA")
        assert "TSLA" in source.get_tickers()
        assert cache.get("TSLA") is not None
        await source.stop()

    async def test_remove_ticker_clears_cache(self):
        cache  = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "TSLA"])
        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()
        assert cache.get("TSLA") is None
        await source.stop()
```

### 13.4 MassiveDataSource (mocked)

```python
# backend/tests/market/test_massive.py
from unittest.mock import MagicMock, patch
import pytest
from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def make_snapshot(ticker: str, price: float, ts_ms: int = 1_707_580_800_000) -> MagicMock:
    snap = MagicMock()
    snap.ticker              = ticker
    snap.last_trade.price    = price
    snap.last_trade.timestamp = ts_ms
    return snap


@pytest.mark.asyncio
class TestMassiveDataSource:

    async def test_poll_updates_cache(self):
        cache  = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "GOOGL"]
        snaps = [make_snapshot("AAPL", 190.50), make_snapshot("GOOGL", 175.25)]

        with patch.object(source, "_fetch_snapshots", return_value=snaps):
            await source._poll_once()

        assert cache.get_price("AAPL")  == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_malformed_snapshot_skipped(self):
        cache  = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "BAD"]
        good = make_snapshot("AAPL", 190.50)
        bad  = MagicMock()
        bad.ticker      = "BAD"
        bad.last_trade  = None    # triggers AttributeError

        with patch.object(source, "_fetch_snapshots", return_value=[good, bad]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD")  is None

    async def test_api_error_does_not_crash(self):
        cache  = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()   # must not raise

    async def test_timestamp_ms_to_seconds(self):
        cache  = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        snap = make_snapshot("AAPL", 190.00, ts_ms=1_707_580_800_000)

        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        assert cache.get("AAPL").timestamp == pytest.approx(1_707_580_800.0, abs=1.0)

    async def test_remove_clears_cache(self):
        cache  = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "GOOGL"]
        cache.update("GOOGL", 175.00)
        await source.remove_ticker("GOOGL")
        assert "GOOGL" not in source.get_tickers()
        assert cache.get("GOOGL") is None
```

### 13.5 Factory

```python
# backend/tests/market/test_factory.py
import os
from unittest.mock import patch
from app.market.factory import create_market_data_source
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource
from app.market.massive_client import MassiveDataSource


def test_no_key_gives_simulator():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        assert isinstance(create_market_data_source(PriceCache()), SimulatorDataSource)

def test_empty_key_gives_simulator():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
        assert isinstance(create_market_data_source(PriceCache()), SimulatorDataSource)

def test_whitespace_key_gives_simulator():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
        assert isinstance(create_market_data_source(PriceCache()), SimulatorDataSource)

def test_real_key_gives_massive():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "a-real-key"}):
        assert isinstance(create_market_data_source(PriceCache()), MassiveDataSource)
```

---

## 14. Error Handling

### Empty watchlist at startup

`start([])` is valid. The simulator produces no prices; the Massive poller
skips the API call. SSE sends empty events. The first `add_ticker()` call
starts data flowing immediately.

### Cache miss during a trade

The simulator seeds prices in `add_ticker()`, so misses are rare. Massive
may have up to a 15 s gap after adding a new ticker. The trade route must
handle the `None` case explicitly:

```python
price = price_cache.get_price(ticker)
if price is None:
    raise HTTPException(400, f"Price not yet available for {ticker}. Try again in a moment.")
```

### Invalid Massive API key

The first poll fails with a 401. The poller logs the error and keeps running
(retrying every 15 s). The cache stays empty; SSE sends no data. The user
sees prices missing in the UI. Fix: correct the key in `.env` and restart.

---

## 15. Configuration Reference

| Parameter | Location | Default | Notes |
|-----------|----------|---------|-------|
| `MASSIVE_API_KEY` | env var | `""` | Empty → simulator; non-empty → Massive |
| `update_interval` | `SimulatorDataSource.__init__` | `0.5 s` | Simulator tick rate |
| `poll_interval` | `MassiveDataSource.__init__` | `15.0 s` | Massive poll cadence |
| `event_probability` | `GBMSimulator.__init__` | `0.001` | Chance of a random shock per ticker per tick |
| `dt` | `GBMSimulator.__init__` | `~8.5e-8` | GBM time step (fraction of a trading year) |
| SSE push interval | `_generate_events()` | `0.5 s` | How often to poll cache and possibly send |
| SSE retry directive | `_generate_events()` | `1000 ms` | Browser `EventSource` reconnection delay |

### `pyproject.toml` — required build config

```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

Without this, `uv sync` and Docker builds fail with
`ValueError: Unable to determine which files to ship inside the wheel`.

### Package `__init__.py`

```python
# backend/app/market/__init__.py
from .cache   import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models  import PriceUpdate
from .stream  import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

Downstream code imports from `app.market` only — never from submodules.
