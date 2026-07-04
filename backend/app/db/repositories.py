"""Repository functions — the only sanctioned way to touch the database.

Every function takes an explicit ``sqlite3.Connection`` so callers can compose
multiple writes into a single transaction (required for atomic trade execution).
Rows are returned as plain JSON-ready ``dict``s; timestamps are ISO-8601 UTC
strings. Tickers are stored and compared uppercased + stripped.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

USER_ID = "default"

DEFAULT_CASH_BALANCE = 10000.0

DEFAULT_TICKERS = (
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

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    """Current time as an ISO-8601 UTC string."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _norm_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _norm_side(side: str) -> str:
    return side.strip().lower()


# --------------------------------------------------------------------------- #
# initialization / seeding
# --------------------------------------------------------------------------- #
def init_db() -> None:
    """Lazy-init the database: create tables and seed defaults if empty.

    Idempotent — safe to call on every startup. Creates the 6 tables from
    ``schema.sql``, then seeds exactly one default profile (``$10,000`` cash)
    and the 10 default watchlist tickers, but only when those tables are empty.
    """
    from .connection import connection

    schema_sql = _SCHEMA_PATH.read_text()
    with connection() as conn:
        conn.executescript(schema_sql)

        profile_count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
        if profile_count == 0:
            conn.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                (USER_ID, DEFAULT_CASH_BALANCE, _now()),
            )

        watchlist_count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        if watchlist_count == 0:
            for ticker in DEFAULT_TICKERS:
                conn.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (_new_id(), USER_ID, ticker, _now()),
                )


# --------------------------------------------------------------------------- #
# users_profile
# --------------------------------------------------------------------------- #
def get_profile(conn: sqlite3.Connection) -> dict:
    """Return the user profile: ``{id, cash_balance, created_at}``."""
    row = conn.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (USER_ID,),
    ).fetchone()
    return dict(row)


def set_cash_balance(conn: sqlite3.Connection, balance: float) -> None:
    """Set the user's cash balance."""
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (float(balance), USER_ID),
    )


# --------------------------------------------------------------------------- #
# watchlist
# --------------------------------------------------------------------------- #
def get_watchlist(conn: sqlite3.Connection) -> list[dict]:
    """Return watchlist rows ``[{id, ticker, added_at}]`` in insertion order."""
    rows = conn.execute(
        "SELECT id, ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY rowid",
        (USER_ID,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_watchlist_ticker(conn: sqlite3.Connection, ticker: str) -> dict:
    """Add a ticker to the watchlist (idempotent); return its row.

    If the ticker is already present, the existing row is returned unchanged.
    """
    ticker = _norm_ticker(ticker)
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (_new_id(), USER_ID, ticker, _now()),
    )
    row = conn.execute(
        "SELECT id, ticker, added_at FROM watchlist WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    ).fetchone()
    return dict(row)


def remove_watchlist_ticker(conn: sqlite3.Connection, ticker: str) -> bool:
    """Remove a ticker; return True if a row was actually deleted."""
    ticker = _norm_ticker(ticker)
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    )
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# positions
# --------------------------------------------------------------------------- #
def get_positions(conn: sqlite3.Connection) -> list[dict]:
    """Return all positions ``[{id, ticker, quantity, avg_cost, updated_at}]``."""
    rows = conn.execute(
        "SELECT id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? ORDER BY ticker",
        (USER_ID,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position(conn: sqlite3.Connection, ticker: str) -> dict | None:
    """Return a single position row, or ``None`` if not held."""
    ticker = _norm_ticker(ticker)
    row = conn.execute(
        "SELECT id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    ).fetchone()
    return dict(row) if row is not None else None


def upsert_position(
    conn: sqlite3.Connection, ticker: str, quantity: float, avg_cost: float
) -> dict:
    """Insert or update a position; return the resulting row.

    The row's ``id`` is preserved across updates.
    """
    ticker = _norm_ticker(ticker)
    now = _now()
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, ticker) DO UPDATE SET "
        "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
        "updated_at = excluded.updated_at",
        (_new_id(), USER_ID, ticker, float(quantity), float(avg_cost), now),
    )
    row = conn.execute(
        "SELECT id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    ).fetchone()
    return dict(row)


def delete_position(conn: sqlite3.Connection, ticker: str) -> None:
    """Delete a position (no-op if absent)."""
    ticker = _norm_ticker(ticker)
    conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (USER_ID, ticker),
    )


# --------------------------------------------------------------------------- #
# trades
# --------------------------------------------------------------------------- #
def record_trade(
    conn: sqlite3.Connection, ticker: str, side: str, quantity: float, price: float
) -> dict:
    """Append a trade to the log; return ``{id, ticker, side, quantity, price, executed_at}``."""
    ticker = _norm_ticker(ticker)
    side = _norm_side(side)
    trade_id = _new_id()
    executed_at = _now()
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, USER_ID, ticker, side, float(quantity), float(price), executed_at),
    )
    return {
        "id": trade_id,
        "ticker": ticker,
        "side": side,
        "quantity": float(quantity),
        "price": float(price),
        "executed_at": executed_at,
    }


def get_trades(conn: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    """Return trades newest-first, optionally limited."""
    sql = (
        "SELECT id, ticker, side, quantity, price, executed_at "
        "FROM trades WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC"
    )
    params: tuple = (USER_ID,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (USER_ID, int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# portfolio_snapshots
# --------------------------------------------------------------------------- #
def record_snapshot(conn: sqlite3.Connection, total_value: float) -> dict:
    """Persist a portfolio-value snapshot; return ``{id, total_value, recorded_at}``."""
    snapshot_id = _new_id()
    recorded_at = _now()
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (snapshot_id, USER_ID, float(total_value), recorded_at),
    )
    return {
        "id": snapshot_id,
        "total_value": float(total_value),
        "recorded_at": recorded_at,
    }


def get_snapshots(conn: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    """Return snapshots oldest→newest (for charting).

    When ``limit`` is given, the most recent ``limit`` snapshots are returned,
    still ordered oldest→newest.
    """
    if limit is None:
        rows = conn.execute(
            "SELECT id, total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY recorded_at ASC, rowid ASC",
            (USER_ID,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, total_value, recorded_at FROM ("
            "  SELECT id, total_value, recorded_at, rowid AS rid FROM portfolio_snapshots "
            "  WHERE user_id = ? ORDER BY recorded_at DESC, rowid DESC LIMIT ?"
            ") ORDER BY recorded_at ASC, rid ASC",
            (USER_ID, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# chat_messages
# --------------------------------------------------------------------------- #
def get_recent_messages(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Return the most recent messages, ordered oldest→newest.

    Each row is ``{id, role, content, actions, created_at}`` with ``actions``
    parsed back to a ``dict`` (or ``None``).
    """
    rows = conn.execute(
        "SELECT id, role, content, actions, created_at FROM ("
        "  SELECT id, role, content, actions, created_at, rowid AS rid FROM chat_messages "
        "  WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?"
        ") ORDER BY created_at ASC, rid ASC",
        (USER_ID, int(limit)),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["actions"] = json.loads(d["actions"]) if d["actions"] is not None else None
        result.append(d)
    return result


def add_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: dict | None = None,
) -> dict:
    """Append a chat message; return the stored row with ``actions`` parsed back.

    ``actions`` is serialized to JSON text for storage and returned as the
    original ``dict`` (or ``None``).
    """
    message_id = _new_id()
    created_at = _now()
    actions_json = json.dumps(actions) if actions is not None else None
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, USER_ID, role, content, actions_json, created_at),
    )
    return {
        "id": message_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": created_at,
    }
