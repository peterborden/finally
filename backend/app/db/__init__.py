"""Database layer for FinAlly.

Public API:
    init_db     - Idempotent lazy init: create tables + seed defaults if empty.
    connection  - Context manager yielding a configured sqlite3.Connection.
    repository functions (per BUILD_CONTRACT §3) — all take an explicit
    connection and return plain JSON-ready dicts with ISO-8601 UTC timestamps.
"""

from .connection import connection, get_db_path
from .repositories import (
    add_message,
    add_watchlist_ticker,
    delete_position,
    get_position,
    get_positions,
    get_profile,
    get_recent_messages,
    get_snapshots,
    get_trades,
    get_watchlist,
    init_db,
    record_snapshot,
    record_trade,
    remove_watchlist_ticker,
    set_cash_balance,
    upsert_position,
)

__all__ = [
    "init_db",
    "connection",
    "get_db_path",
    # users_profile
    "get_profile",
    "set_cash_balance",
    # watchlist
    "get_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    # positions
    "get_positions",
    "get_position",
    "upsert_position",
    "delete_position",
    # trades
    "record_trade",
    "get_trades",
    # portfolio_snapshots
    "record_snapshot",
    "get_snapshots",
    # chat_messages
    "get_recent_messages",
    "add_message",
]
