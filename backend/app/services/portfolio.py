"""Portfolio service: trade execution, portfolio valuation, snapshots.

Consumes the DB repository layer (``app.db``, contract §3) and the market
``PriceCache`` (contract §4). All trade mutations happen inside ONE DB
transaction so a partially-applied trade can never be observed.

``db`` is imported through a module-level indirection so this module still
imports when the DB layer (built in a parallel worktree) is absent — unit tests
patch ``app.services.portfolio.db`` with a fake/mock.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

try:  # DB layer is owned by another worktree; may be absent here.
    from app import db as db
except ImportError:  # pragma: no cover - exercised only pre-merge
    db = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Below this absolute quantity a position is considered fully closed.
_EPSILON = 1e-9

VALID_SIDES = {"buy", "sell"}


@dataclass
class TradeResult:
    """Outcome of an attempted trade. Never raised — always returned."""

    success: bool
    error: str | None
    trade: dict | None          # recorded trade row, if filled
    position: dict | None       # resulting position row (None if fully sold)
    cash_balance: float


def _normalize_ticker(ticker: str) -> str:
    return (ticker or "").strip().upper()


def execute_trade(ticker: str, side: str, quantity: float, price_cache) -> TradeResult:
    """Execute a market order at the current cache price in one transaction.

    Validation (returns ``success=False`` rather than raising):
      * side must be 'buy' or 'sell'
      * quantity must be > 0
      * a live price must exist in the cache
      * buys require sufficient cash; sells require sufficient shares

    On success: updates the position (weighted-average cost on buy), adjusts
    cash, records the trade, and records a portfolio snapshot — all atomically.
    """
    ticker = _normalize_ticker(ticker)
    side = (side or "").strip().lower()

    if side not in VALID_SIDES:
        return _fail(f"Invalid side {side!r}; must be 'buy' or 'sell'", price_cache)

    if quantity is None or quantity <= 0:
        return _fail("Quantity must be positive", price_cache)

    price = price_cache.get_price(ticker)
    if price is None:
        return _fail(f"No price available for {ticker}", price_cache)

    with db.connection() as conn:
        profile = db.get_profile(conn)
        cash = float(profile["cash_balance"])
        existing = db.get_position(conn, ticker)

        if side == "buy":
            cost = quantity * price
            if cost > cash + _EPSILON:
                return TradeResult(
                    success=False,
                    error=f"Insufficient cash: need ${cost:.2f}, have ${cash:.2f}",
                    trade=None,
                    position=existing,
                    cash_balance=round(cash, 2),
                )
            old_qty = float(existing["quantity"]) if existing else 0.0
            old_avg = float(existing["avg_cost"]) if existing else 0.0
            new_qty = old_qty + quantity
            new_avg = (old_qty * old_avg + quantity * price) / new_qty
            new_cash = cash - cost
            position = db.upsert_position(conn, ticker, round(new_qty, 8), round(new_avg, 6))
        else:  # sell
            owned = float(existing["quantity"]) if existing else 0.0
            if owned + _EPSILON < quantity:
                return TradeResult(
                    success=False,
                    error=(
                        f"Insufficient shares: trying to sell {quantity:g} of "
                        f"{ticker}, own {owned:g}"
                    ),
                    trade=None,
                    position=existing,
                    cash_balance=round(cash, 2),
                )
            proceeds = quantity * price
            new_qty = owned - quantity
            new_cash = cash + proceeds
            if new_qty <= _EPSILON:
                db.delete_position(conn, ticker)
                position = None
            else:
                avg = float(existing["avg_cost"])
                position = db.upsert_position(conn, ticker, round(new_qty, 8), round(avg, 6))

        new_cash = round(new_cash, 2)
        db.set_cash_balance(conn, new_cash)
        trade = db.record_trade(conn, ticker, side, quantity, price)

        total_value = _compute_total_value(conn, new_cash, price_cache)
        db.record_snapshot(conn, total_value)

    return TradeResult(
        success=True,
        error=None,
        trade=trade,
        position=position,
        cash_balance=new_cash,
    )


def _fail(message: str, price_cache) -> TradeResult:
    """Build a failure result, reporting the current (unchanged) cash balance."""
    try:
        with db.connection() as conn:
            cash = round(float(db.get_profile(conn)["cash_balance"]), 2)
    except Exception:  # pragma: no cover - defensive; DB unavailable
        cash = 0.0
    return TradeResult(success=False, error=message, trade=None, position=None,
                       cash_balance=cash)


def _position_valuation(position: dict, price_cache) -> dict:
    """Compute the §5.1 per-position view. Null price contributes 0 to totals."""
    ticker = position["ticker"]
    qty = float(position["quantity"])
    avg_cost = float(position["avg_cost"])
    price = price_cache.get_price(ticker)

    if price is None:
        return {
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": round(avg_cost, 4),
            "current_price": None,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_percent": 0.0,
        }

    market_value = qty * price
    cost_basis = qty * avg_cost
    pnl = market_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
    return {
        "ticker": ticker,
        "quantity": qty,
        "avg_cost": round(avg_cost, 4),
        "current_price": round(price, 2),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(pnl, 2),
        "unrealized_pnl_percent": round(pnl_pct, 2),
    }


def get_portfolio_state(price_cache) -> dict:
    """Assemble the GET /api/portfolio response shape (§5.1)."""
    with db.connection() as conn:
        cash = round(float(db.get_profile(conn)["cash_balance"]), 2)
        rows = db.get_positions(conn)

    positions = [_position_valuation(r, price_cache) for r in rows]
    positions_value = round(sum(p["market_value"] for p in positions), 2)
    total_pnl = round(sum(p["unrealized_pnl"] for p in positions), 2)
    return {
        "cash_balance": cash,
        "positions_value": positions_value,
        "total_value": round(cash + positions_value, 2),
        "total_unrealized_pnl": total_pnl,
        "positions": positions,
    }


def _compute_total_value(conn, cash: float, price_cache) -> float:
    """Total portfolio value = cash + live market value of all positions."""
    total = cash
    for row in db.get_positions(conn):
        price = price_cache.get_price(row["ticker"])
        if price is not None:
            total += float(row["quantity"]) * price
    return round(total, 2)


def record_portfolio_snapshot(price_cache) -> dict:
    """Compute total value from cash + live position values; persist a snapshot."""
    with db.connection() as conn:
        cash = float(db.get_profile(conn)["cash_balance"])
        total_value = _compute_total_value(conn, cash, price_cache)
        return db.record_snapshot(conn, total_value)


def get_history(limit: int | None = None) -> list[dict]:
    """Return portfolio value snapshots, oldest→newest (for the P&L chart)."""
    with db.connection() as conn:
        return db.get_snapshots(conn, limit)


async def snapshot_loop(price_cache, interval: float = 30.0) -> None:
    """Background task: record a portfolio snapshot every ``interval`` seconds.

    Runs until cancelled (app shutdown). Individual failures are logged and do
    not stop the loop.
    """
    logger.info("Portfolio snapshot loop started (interval=%.0fs)", interval)
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                await asyncio.to_thread(record_portfolio_snapshot, price_cache)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to record portfolio snapshot")
    except asyncio.CancelledError:
        logger.info("Portfolio snapshot loop stopped")
        raise
