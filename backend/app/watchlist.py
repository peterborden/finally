"""Watchlist REST API: view, add, and remove watched tickers.

Backed by the Phase 1 SQLite `watchlist` table for persistence and the
shared `PriceCache` on `app.state` for live prices. Add/remove operations
also drive the running `MarketDataSource` (via `app.state.market_source`)
so a ticker starts/stops streaming immediately.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from .db import get_connection, get_db_path
from .market import MarketDataSource, PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_USER_ID = "default"


def _normalize_ticker(value: str) -> str:
    """Upper-case and strip a ticker so "aapl " and "AAPL" collide."""
    return value.strip().upper()


async def add_ticker(
    conn: sqlite3.Connection, market_source: MarketDataSource | None, ticker: str
) -> str:
    """Add `ticker` to the default user's watchlist; idempotent.

    Reusable service function shared by the watchlist HTTP router (plan
    02-01) and the AI chat auto-execution path (plan 03-03). Takes an
    already-open connection so the caller controls commit/close; the
    caller is responsible for reading back any row it needs afterward.
    """
    normalized = _normalize_ticker(ticker)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (uuid.uuid4().hex, _USER_ID, normalized, now),
    )
    conn.commit()

    if market_source is not None:
        await market_source.add_ticker(normalized)
    else:
        logger.warning(
            "market_source unavailable; %s added to DB but not streaming", normalized
        )

    return normalized


async def remove_ticker(
    conn: sqlite3.Connection, market_source: MarketDataSource | None, ticker: str
) -> bool:
    """Remove `ticker` from the default user's watchlist; idempotent.

    Returns whether a row was actually removed. Reusable service function
    shared by the watchlist HTTP router and the AI chat auto-execution path.
    """
    normalized = _normalize_ticker(ticker)

    cursor = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (_USER_ID, normalized),
    )
    conn.commit()
    removed = cursor.rowcount > 0

    if market_source is not None:
        await market_source.remove_ticker(normalized)
    else:
        logger.warning(
            "market_source unavailable; %s removed from DB but not stopped", normalized
        )

    return removed


class WatchlistAddRequest(BaseModel):
    """Request body for POST /api/watchlist."""

    ticker: str

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _normalize_ticker(value)


class WatchlistEntry(BaseModel):
    """A single watchlist row joined with its latest cached price."""

    ticker: str
    price: float | None = None
    previous_price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    direction: str | None = None
    added_at: str | None = None


def create_watchlist_router() -> APIRouter:
    """Create the watchlist router (factory pattern, no module-level globals).

    Cache and market source are read per-request from `request.app.state`
    rather than captured at factory time, since the market source is only
    assigned once the app's lifespan has run.
    """

    @router.get("")
    async def list_watchlist(request: Request) -> list[WatchlistEntry]:
        """GET /api/watchlist — every watched ticker with its latest price."""
        conn = get_connection(get_db_path())
        try:
            rows = conn.execute(
                "SELECT ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at",
                (_USER_ID,),
            ).fetchall()
        finally:
            conn.close()

        cache = request.app.state.price_cache
        return [_build_entry(cache, row["ticker"], row["added_at"]) for row in rows]

    @router.post("", status_code=201)
    async def post_ticker(body: WatchlistAddRequest, request: Request) -> WatchlistEntry:
        """POST /api/watchlist — add a ticker; safe no-op if already present."""
        market_source = request.app.state.market_source

        conn = get_connection(get_db_path())
        try:
            normalized = await add_ticker(conn, market_source, body.ticker)
            row = conn.execute(
                "SELECT ticker, added_at FROM watchlist WHERE user_id = ? AND ticker = ?",
                (_USER_ID, normalized),
            ).fetchone()
        finally:
            conn.close()

        cache = request.app.state.price_cache
        added_at = row["added_at"] if row is not None else datetime.now(timezone.utc).isoformat()
        return _build_entry(cache, normalized, added_at)

    @router.delete("/{ticker}")
    async def delete_ticker(ticker: str, request: Request) -> dict[str, str | bool]:
        """DELETE /api/watchlist/{ticker} — idempotent removal."""
        market_source = request.app.state.market_source

        conn = get_connection(get_db_path())
        try:
            removed = await remove_ticker(conn, market_source, ticker)
        finally:
            conn.close()

        return {"ticker": _normalize_ticker(ticker), "removed": removed}

    return router


def _build_entry(cache: PriceCache, ticker: str, added_at: str | None) -> WatchlistEntry:
    """Join a watchlist row with its latest cached price, if any."""
    update = cache.get(ticker)
    if update is None:
        return WatchlistEntry(ticker=ticker, added_at=added_at)

    return WatchlistEntry(
        ticker=ticker,
        price=update.price,
        previous_price=update.previous_price,
        change=update.change,
        change_percent=update.change_percent,
        direction=update.direction,
        added_at=added_at,
    )
