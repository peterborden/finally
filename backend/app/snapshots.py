"""Background task that periodically records a portfolio value snapshot.

Runs an async loop that calls `app.portfolio.compute_and_record_snapshot`
every `interval` seconds, using a fresh SQLite connection per tick (the
periodic task lives outside any HTTP request, so it cannot reuse a
request-scoped connection). This is the periodic half of PORT-06; the
immediate half is recorded inline by `app.portfolio.execute_trade` right
after a trade. Both paths call the same helper so there is exactly one
way to write a `portfolio_snapshots` row.
"""

from __future__ import annotations

import asyncio
import logging
import os

from .db import get_connection, get_db_path
from .market import PriceCache
from .portfolio import compute_and_record_snapshot

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 30.0
_INTERVAL_ENV_VAR = "SNAPSHOT_INTERVAL_SECONDS"


def _resolve_interval() -> float:
    """Read the snapshot interval from env, defaulting to 30s.

    Falls back to DEFAULT_INTERVAL_SECONDS (with a warning logged) when the
    env var is absent, non-numeric, or not strictly positive -- a bad or
    tampered value must never disable or busy-loop the periodic task.
    """
    raw = os.environ.get(_INTERVAL_ENV_VAR)
    if raw is None:
        return DEFAULT_INTERVAL_SECONDS

    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not a valid number; falling back to %.1fs",
            _INTERVAL_ENV_VAR,
            raw,
            DEFAULT_INTERVAL_SECONDS,
        )
        return DEFAULT_INTERVAL_SECONDS

    if value <= 0:
        logger.warning(
            "%s=%r must be positive; falling back to %.1fs",
            _INTERVAL_ENV_VAR,
            raw,
            DEFAULT_INTERVAL_SECONDS,
        )
        return DEFAULT_INTERVAL_SECONDS

    return value


class SnapshotRecorder:
    """Periodically records a portfolio_snapshots row on a background task.

    Mirrors the start/stop asyncio task lifecycle of
    `app.market.simulator.SimulatorDataSource`: `start()` creates a named
    background task, `stop()` cancels it and awaits completion, swallowing
    CancelledError so shutdown is clean.
    """

    def __init__(self, interval: float | None = None) -> None:
        self._interval = interval if interval is not None else _resolve_interval()
        self._task: asyncio.Task | None = None

    def start(self, price_cache: PriceCache) -> None:
        """Start the periodic snapshot loop as a named background task."""
        self._task = asyncio.create_task(
            self._run_loop(price_cache), name="portfolio-snapshotter"
        )
        logger.info("Portfolio snapshotter started (interval=%.2fs)", self._interval)

    async def stop(self) -> None:
        """Cancel the background task and await its completion."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Portfolio snapshotter stopped")

    async def _run_loop(self, price_cache: PriceCache) -> None:
        """Core loop: sleep, record a snapshot, repeat.

        Sleeping first means the task never races the DB's lazy
        initialization (the first HTTP request creates the schema; see
        `app.main`'s `ensure_database` middleware) by trying to write a
        snapshot before any table exists. A fresh connection is opened,
        committed, and closed each tick so a bad tick never leaks a
        connection. Errors (DB or valuation) are logged and the loop
        continues on the next interval rather than killing the task.
        """
        while True:
            await asyncio.sleep(self._interval)
            try:
                conn = get_connection(get_db_path())
                try:
                    compute_and_record_snapshot(conn, price_cache)
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                logger.exception("Portfolio snapshot tick failed")
