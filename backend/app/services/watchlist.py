"""Watchlist service: keep the DB watchlist and the market data source in sync.

The market source's ``add_ticker`` / ``remove_ticker`` are async, so these
service functions are async and are awaited by the routers (and by the LLM chat
auto-execution path).
"""

from __future__ import annotations

import logging

try:  # DB layer owned by another worktree; may be absent here.
    from app import db as db
except ImportError:  # pragma: no cover - exercised only pre-merge
    db = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _normalize_ticker(ticker: str) -> str:
    return (ticker or "").strip().upper()


async def add_ticker(ticker: str, source, price_cache=None) -> dict:
    """Add a ticker to the DB watchlist and start tracking it in the source.

    Idempotent (mirrors ``db.add_watchlist_ticker``). Returns the watchlist row.
    """
    ticker = _normalize_ticker(ticker)
    with db.connection() as conn:
        row = db.add_watchlist_ticker(conn, ticker)
    if source is not None:
        await source.add_ticker(ticker)
    logger.info("Watchlist add: %s", ticker)
    return row


async def remove_ticker(ticker: str, source) -> bool:
    """Remove a ticker from the DB watchlist and stop tracking it in the source.

    Returns True if a watchlist row was actually removed.
    """
    ticker = _normalize_ticker(ticker)
    with db.connection() as conn:
        removed = db.remove_watchlist_ticker(conn, ticker)
    if source is not None:
        await source.remove_ticker(ticker)
    logger.info("Watchlist remove: %s (existed=%s)", ticker, removed)
    return removed


def get_watchlist(price_cache) -> list[dict]:
    """Return the watchlist with latest prices, in the §5.4 per-item shape.

    Price fields are ``null`` until the first tick for a ticker arrives.
    """
    with db.connection() as conn:
        rows = db.get_watchlist(conn)
    return [watchlist_item(r["ticker"], price_cache) for r in rows]


def watchlist_item(ticker: str, price_cache) -> dict:
    """Build one §5.4 watchlist entry from the cache (daily change vs reference)."""
    update = price_cache.get(ticker) if price_cache is not None else None
    if update is None:
        return {
            "ticker": ticker,
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": None,
        }
    reference = (
        update.reference_price
        if update.reference_price is not None
        else update.previous_price
    )
    return {
        "ticker": ticker,
        "price": update.price,
        "previous_price": round(reference, 2),
        "change": update.daily_change,
        "change_percent": update.daily_change_percent,
        "direction": update.direction,
    }
