"""In-memory fake of the DB repository layer (contract §3).

Faithfully implements the repository functions over plain dicts so service and
route tests can exercise real trade math / state assembly without the actual
SQLite layer (built in a parallel worktree). Injected by patching
``app.services.portfolio.db`` / ``app.services.watchlist.db``.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeDB:
    """Dict-backed stand-in for ``app.db``. ``conn`` args are accepted and ignored."""

    def __init__(self, cash: float = 10000.0, positions: dict | None = None):
        self._profile = {"id": "default", "cash_balance": cash, "created_at": _now()}
        self._positions: dict[str, dict] = {}
        self._trades: list[dict] = []
        self._snapshots: list[dict] = []
        self._watchlist: list[dict] = []
        self.init_called = False
        if positions:
            for ticker, (qty, avg) in positions.items():
                self.upsert_position(None, ticker, qty, avg)

    def init_db(self) -> None:
        self.init_called = True

    @contextlib.contextmanager
    def connection(self):
        yield self

    # --- users_profile ---
    def get_profile(self, conn) -> dict:
        return dict(self._profile)

    def set_cash_balance(self, conn, balance: float) -> None:
        self._profile["cash_balance"] = balance

    # --- watchlist ---
    def get_watchlist(self, conn) -> list[dict]:
        return [dict(r) for r in self._watchlist]

    def add_watchlist_ticker(self, conn, ticker: str) -> dict:
        for r in self._watchlist:
            if r["ticker"] == ticker:
                return dict(r)
        row = {"id": str(uuid.uuid4()), "ticker": ticker, "added_at": _now()}
        self._watchlist.append(row)
        return dict(row)

    def remove_watchlist_ticker(self, conn, ticker: str) -> bool:
        before = len(self._watchlist)
        self._watchlist = [r for r in self._watchlist if r["ticker"] != ticker]
        return len(self._watchlist) < before

    # --- positions ---
    def get_positions(self, conn) -> list[dict]:
        return [dict(r) for r in self._positions.values()]

    def get_position(self, conn, ticker: str) -> dict | None:
        row = self._positions.get(ticker)
        return dict(row) if row else None

    def upsert_position(self, conn, ticker: str, quantity: float, avg_cost: float) -> dict:
        existing = self._positions.get(ticker)
        row = {
            "id": existing["id"] if existing else str(uuid.uuid4()),
            "ticker": ticker,
            "quantity": quantity,
            "avg_cost": avg_cost,
            "updated_at": _now(),
        }
        self._positions[ticker] = row
        return dict(row)

    def delete_position(self, conn, ticker: str) -> None:
        self._positions.pop(ticker, None)

    # --- trades ---
    def record_trade(self, conn, ticker: str, side: str, quantity: float, price: float) -> dict:
        row = {
            "id": str(uuid.uuid4()),
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": _now(),
        }
        self._trades.append(row)
        return dict(row)

    def get_trades(self, conn, limit: int | None = None) -> list[dict]:
        rows = [dict(r) for r in reversed(self._trades)]
        return rows[:limit] if limit else rows

    # --- portfolio_snapshots ---
    def record_snapshot(self, conn, total_value: float) -> dict:
        row = {"id": str(uuid.uuid4()), "total_value": total_value, "recorded_at": _now()}
        self._snapshots.append(row)
        return dict(row)

    def get_snapshots(self, conn, limit: int | None = None) -> list[dict]:
        rows = [dict(r) for r in self._snapshots]
        return rows[-limit:] if limit else rows
