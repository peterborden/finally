"""Pure trade math and validation for buy/sell market orders.

This module has no dependency on the database, FastAPI, or `app.market` --
it is a set of pure functions operating on plain values so that the trade
math (average-cost accounting, cash movement, fractional shares, and the
insufficient-cash / insufficient-shares rejections) can be proven correct
in isolation. Both the manual-trade HTTP endpoint (plan 02-03) and the
AI-driven trade path (Phase 3) call `apply_trade` to share one validated
implementation.

Nothing here performs I/O or mutates its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Floating-point residue below this threshold is treated as a fully-sold
# (zero) position, so dust left over from repeated float arithmetic doesn't
# leave an un-sellable phantom position (T-02-05).
QUANTITY_EPSILON = 1e-9


class Side(str, Enum):
    """Direction of a trade: buy (long) or sell (reduce/close)."""

    BUY = "buy"
    SELL = "sell"


class TradeError(Exception):
    """Raised when a trade request fails validation.

    Carries a human-readable message describing why the trade was rejected
    (invalid input, insufficient cash, or insufficient shares) so the
    caller (HTTP endpoint or LLM chat) can surface it to the user. No
    applied state is returned when this is raised -- the caller's cash and
    position are left exactly as passed in.
    """


@dataclass(frozen=True, slots=True)
class Position:
    """Immutable snapshot of a holding in a single ticker.

    A fresh / non-existent position is represented as quantity=0.0,
    avg_cost=0.0.
    """

    quantity: float
    avg_cost: float


@dataclass(frozen=True, slots=True)
class TradeResult:
    """Outcome of a successfully-applied trade.

    Carries the full resulting state so the caller can persist it (upsert
    position, update cash balance, append a trade row) without recomputing
    any math itself.
    """

    new_cash: float
    new_quantity: float
    new_avg_cost: float
    remove_position: bool
    filled_quantity: float
    filled_price: float


def _validate_inputs(quantity: float, price: float) -> None:
    """Reject non-positive quantity or price before any math is applied."""
    if quantity <= 0:
        raise TradeError(f"Quantity must be positive, got {quantity}")
    if price <= 0:
        raise TradeError(f"Price must be positive, got {price}")


def _apply_buy(quantity: float, price: float, cash: float, position: Position) -> TradeResult:
    """Compute the result of a buy order.

    new_cash = cash - qty*price
    new_qty = old_qty + qty
    new_avg = (old_qty*old_avg + qty*price) / (old_qty + qty)

    A fresh position (old_qty == 0) yields new_avg == price.
    """
    cost = quantity * price
    if cash < cost:
        shortfall = cost - cash
        raise TradeError(
            f"Insufficient cash: need {cost:.2f}, have {cash:.2f} "
            f"(short {shortfall:.2f})"
        )

    new_quantity = position.quantity + quantity
    new_avg_cost = (position.quantity * position.avg_cost + cost) / new_quantity

    return TradeResult(
        new_cash=cash - cost,
        new_quantity=new_quantity,
        new_avg_cost=new_avg_cost,
        remove_position=False,
        filled_quantity=quantity,
        filled_price=price,
    )


def _apply_sell(quantity: float, price: float, cash: float, position: Position) -> TradeResult:
    """Compute the result of a sell order.

    new_cash = cash + qty*price
    new_qty = old_qty - qty (avg_cost unchanged)

    A resulting quantity within QUANTITY_EPSILON of zero flags
    remove_position so the caller deletes the position row rather than
    persisting floating-point dust.
    """
    if position.quantity < quantity - QUANTITY_EPSILON:
        raise TradeError(
            f"Insufficient shares: requested {quantity}, held {position.quantity}"
        )

    remaining = position.quantity - quantity
    remove_position = abs(remaining) <= QUANTITY_EPSILON

    return TradeResult(
        new_cash=cash + quantity * price,
        new_quantity=0.0 if remove_position else remaining,
        new_avg_cost=position.avg_cost,
        remove_position=remove_position,
        filled_quantity=quantity,
        filled_price=price,
    )


def apply_trade(
    *,
    side: Side,
    quantity: float,
    price: float,
    cash: float,
    position: Position,
) -> TradeResult:
    """Validate and compute the result of a market order.

    Pure function: never mutates `position`, never performs I/O. Returns a
    `TradeResult` describing the fully-resolved new state on success, or
    raises `TradeError` with a descriptive message on any rejection
    (invalid quantity/price, insufficient cash, or insufficient shares).
    The caller is responsible for persisting the returned state; on
    rejection no state should be persisted at all.
    """
    _validate_inputs(quantity, price)

    if side == Side.BUY:
        return _apply_buy(quantity, price, cash, position)
    return _apply_sell(quantity, price, cash, position)
