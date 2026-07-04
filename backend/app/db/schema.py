"""SQLite schema DDL for the FinAlly persistence layer.

Defines the six-table schema per planning/PLAN.md §7. All statements use
CREATE TABLE IF NOT EXISTS so re-running init is always safe.
"""

from __future__ import annotations

TABLE_NAMES: tuple[str, ...] = (
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
)

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users_profile (
        id TEXT PRIMARY KEY DEFAULT 'default',
        cash_balance REAL DEFAULT 10000.0,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        ticker TEXT,
        added_at TEXT,
        UNIQUE(user_id, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        ticker TEXT,
        quantity REAL,
        avg_cost REAL,
        updated_at TEXT,
        UNIQUE(user_id, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        ticker TEXT,
        side TEXT,
        quantity REAL,
        price REAL,
        executed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        total_value REAL,
        recorded_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'default',
        role TEXT,
        content TEXT,
        actions TEXT,
        created_at TEXT
    )
    """,
)
