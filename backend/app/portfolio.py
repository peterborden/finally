"""Portfolio and trading REST API: valuation, market-order execution, history.

Reads live prices from the shared `PriceCache` (never a market data source
directly -- see codebase ARCHITECTURE.md anti-patterns) and delegates all
trade math/validation to the pure `app.trade_engine.apply_trade`. This
module owns persistence: reading/writing `users_profile`, `positions`,
`trades`, and `portfolio_snapshots`.

The service functions (`build_portfolio`, `execute_trade`,
`compute_and_record_snapshot`) take a `sqlite3.Connection` and a
`PriceCache` directly -- no FastAPI dependency -- so they are unit-testable
and reusable by the plan 02-04 background snapshot task and by Phase 3's
AI-driven trade path.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from .db import get_connection, get_db_path
from .market import PriceCache
from .trade_engine import Position, Side, TradeError, TradeResult, apply_trade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_USER_ID = "default"


# --- Service layer -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class PositionView:
    """A position joined with its live valuation."""

    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    pct_change: float


@dataclass(frozen=True, slots=True)
class PortfolioView:
    """The full portfolio snapshot returned by GET /api/portfolio."""

    cash_balance: float
    positions: list[PositionView]
    total_value: float
    total_unrealized_pnl: float


@dataclass(frozen=True, slots=True)
class _PositionRow:
    """A raw position row (ticker, quantity, avg_cost) as stored in SQLite."""

    ticker: str
    quantity: float
    avg_cost: float


def read_cash(conn: sqlite3.Connection) -> float:
    """Read the default user's cash balance."""
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (_USER_ID,)
    ).fetchone()
    return float(row["cash_balance"]) if row is not None else 0.0


def read_positions(conn: sqlite3.Connection) -> list[_PositionRow]:
    """Read all held positions for the default user."""
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ?",
        (_USER_ID,),
    ).fetchall()
    return [
        _PositionRow(ticker=row["ticker"], quantity=row["quantity"], avg_cost=row["avg_cost"])
        for row in rows
    ]


def _read_position(conn: sqlite3.Connection, ticker: str) -> _PositionRow:
    """Read a single position, or a zero-quantity placeholder if not held."""
    row = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (_USER_ID, ticker),
    ).fetchone()
    if row is None:
        return _PositionRow(ticker=ticker, quantity=0.0, avg_cost=0.0)
    return _PositionRow(ticker=row["ticker"], quantity=row["quantity"], avg_cost=row["avg_cost"])


def build_portfolio(conn: sqlite3.Connection, price_cache: PriceCache) -> PortfolioView:
    """Compute the full portfolio view: cash, valued positions, totals.

    Valuation rule: current_price comes from `price_cache.get_price(ticker)`.
    When the cache has no price for a held ticker (e.g. it was never
    streamed), the position is valued at its own `avg_cost` instead so
    `total_value` stays finite rather than raising or propagating None --
    unrealized_pnl is then exactly 0 for that position until a live price
    arrives.

    unrealized_pnl = (current_price - avg_cost) * quantity
    pct_change = current_price / avg_cost - 1 (0.0 when avg_cost == 0, to
    avoid a ZeroDivisionError on a degenerate position)
    total_value = cash + sum(quantity * current_price)
    """
    cash = read_cash(conn)
    positions = read_positions(conn)

    position_views: list[PositionView] = []
    total_unrealized_pnl = 0.0
    total_position_value = 0.0

    for position in positions:
        current_price = price_cache.get_price(position.ticker)
        if current_price is None:
            current_price = position.avg_cost

        unrealized_pnl = (current_price - position.avg_cost) * position.quantity
        pct_change = (current_price / position.avg_cost - 1) if position.avg_cost != 0 else 0.0

        position_views.append(
            PositionView(
                ticker=position.ticker,
                quantity=position.quantity,
                avg_cost=position.avg_cost,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                pct_change=pct_change,
            )
        )
        total_unrealized_pnl += unrealized_pnl
        total_position_value += position.quantity * current_price

    total_value = cash + total_position_value

    return PortfolioView(
        cash_balance=cash,
        positions=position_views,
        total_value=total_value,
        total_unrealized_pnl=total_unrealized_pnl,
    )


def compute_and_record_snapshot(conn: sqlite3.Connection, price_cache: PriceCache) -> float:
    """Compute total portfolio value and INSERT a portfolio_snapshots row.

    Returns the recorded total_value. Does NOT commit -- the caller is
    responsible for committing (this lets `execute_trade` fold the snapshot
    into the same transaction as the trade, and lets the plan 02-04
    background task commit on its own cadence).
    """
    portfolio = build_portfolio(conn, price_cache)
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (
            uuid.uuid4().hex,
            _USER_ID,
            portfolio.total_value,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return portfolio.total_value


def execute_trade(
    conn: sqlite3.Connection,
    price_cache: PriceCache,
    ticker: str,
    side: Side,
    quantity: float,
) -> TradeResult:
    """Validate, apply, and persist a market order in a single transaction.

    Reads the current price from `price_cache`, applies `apply_trade` (pure
    trade math from `app.trade_engine`), and on success: updates
    `users_profile.cash_balance`, upserts or deletes the `positions` row,
    appends a `trades` row, records an immediate snapshot via
    `compute_and_record_snapshot`, and commits once.

    On a `TradeError` (invalid input, no cached price, insufficient
    cash/shares) nothing is written and the connection is never committed --
    the exception propagates so the caller (router) can map it to HTTP 400
    and the DB is left exactly as it was.
    """
    price = price_cache.get_price(ticker)
    if price is None:
        raise TradeError(f"No current price available for {ticker}")

    cash = read_cash(conn)
    existing = _read_position(conn, ticker)

    result = apply_trade(
        side=side,
        quantity=quantity,
        price=price,
        cash=cash,
        position=Position(quantity=existing.quantity, avg_cost=existing.avg_cost),
    )

    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (result.new_cash, _USER_ID),
    )

    if result.remove_position:
        conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
            (_USER_ID, ticker),
        )
    else:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, ticker) DO UPDATE SET "
            "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
            "updated_at = excluded.updated_at",
            (uuid.uuid4().hex, _USER_ID, ticker, result.new_quantity, result.new_avg_cost, now),
        )

    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, _USER_ID, ticker, side.value, result.filled_quantity, result.filled_price, now),
    )

    compute_and_record_snapshot(conn, price_cache)

    conn.commit()

    return result


# --- HTTP layer ----------------------------------------------------------


def _normalize_ticker(value: str) -> str:
    """Upper-case and strip a ticker so "aapl " and "AAPL" collide."""
    return value.strip().upper()


class TradeRequest(BaseModel):
    """Request body for POST /api/portfolio/trade."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _normalize_ticker(value)


class PositionResponse(BaseModel):
    """A single position in the portfolio response."""

    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    pct_change: float


class PortfolioResponse(BaseModel):
    """Response body for GET /api/portfolio and the post-trade payload."""

    cash_balance: float
    positions: list[PositionResponse]
    total_value: float
    total_unrealized_pnl: float


class TradeResponse(BaseModel):
    """Response body for POST /api/portfolio/trade: the fill plus fresh portfolio."""

    ticker: str
    side: Literal["buy", "sell"]
    filled_quantity: float
    filled_price: float
    portfolio: PortfolioResponse


class SnapshotResponse(BaseModel):
    """A single row from portfolio_snapshots."""

    id: str
    total_value: float
    recorded_at: str


def _to_portfolio_response(portfolio: PortfolioView) -> PortfolioResponse:
    return PortfolioResponse(
        cash_balance=portfolio.cash_balance,
        positions=[
            PositionResponse(
                ticker=p.ticker,
                quantity=p.quantity,
                avg_cost=p.avg_cost,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                pct_change=p.pct_change,
            )
            for p in portfolio.positions
        ],
        total_value=portfolio.total_value,
        total_unrealized_pnl=portfolio.total_unrealized_pnl,
    )


def create_portfolio_router() -> APIRouter:
    """Create the portfolio router (factory pattern, no module-level globals).

    The DB connection and price cache are obtained per-request: the cache
    from `request.app.state.price_cache`, the connection freshly via
    `get_connection(get_db_path())` with a finally-close.
    """

    @router.get("")
    async def get_portfolio(request: Request) -> PortfolioResponse:
        """GET /api/portfolio (PORT-01)."""
        cache = request.app.state.price_cache
        conn = get_connection(get_db_path())
        try:
            portfolio = build_portfolio(conn, cache)
        finally:
            conn.close()
        return _to_portfolio_response(portfolio)

    @router.post("/trade")
    async def trade(body: TradeRequest, request: Request) -> TradeResponse:
        """POST /api/portfolio/trade (PORT-02, PORT-03, PORT-04, PORT-06)."""
        cache = request.app.state.price_cache
        conn = get_connection(get_db_path())
        try:
            try:
                result = execute_trade(
                    conn, cache, body.ticker, Side(body.side), body.quantity
                )
            except TradeError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            portfolio = build_portfolio(conn, cache)
        finally:
            conn.close()

        return TradeResponse(
            ticker=body.ticker,
            side=body.side,
            filled_quantity=result.filled_quantity,
            filled_price=result.filled_price,
            portfolio=_to_portfolio_response(portfolio),
        )

    @router.get("/history")
    async def get_history(request: Request) -> list[SnapshotResponse]:
        """GET /api/portfolio/history (PORT-05)."""
        conn = get_connection(get_db_path())
        try:
            rows = conn.execute(
                "SELECT id, total_value, recorded_at FROM portfolio_snapshots "
                "WHERE user_id = ? ORDER BY recorded_at",
                (_USER_ID,),
            ).fetchall()
        finally:
            conn.close()

        return [
            SnapshotResponse(id=row["id"], total_value=row["total_value"], recorded_at=row["recorded_at"])
            for row in rows
        ]

    return router
