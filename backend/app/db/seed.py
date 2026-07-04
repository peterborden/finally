"""Default seed data for a fresh FinAlly database."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default watchlist tickers, in PLAN.md §7 order. Kept consistent with
# app.market.seed_prices.SEED_PRICES keys, but defined explicitly here so the
# db package stays importable without the market subsystem.
DEFAULT_TICKERS: tuple[str, ...] = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)

DEFAULT_CASH: float = 10000.0


def seed_defaults(conn: sqlite3.Connection) -> None:
    """Insert the default user profile and watchlist if not already present.

    Idempotent: uses INSERT OR IGNORE keyed on the users_profile id and the
    watchlist UNIQUE(user_id, ticker) constraint, so calling this repeatedly
    never creates duplicates and never raises.
    """
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        ("default", DEFAULT_CASH, now),
    )

    for ticker in DEFAULT_TICKERS:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (uuid.uuid4().hex, "default", ticker, now),
        )

    conn.commit()
