"""Portfolio router: state, trade execution, value history (§5.1–5.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services import portfolio as portfolio_service

from .deps import get_price_cache

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    quantity: float
    side: str


def _serialize_trade(trade: dict) -> dict:
    return {
        "ticker": trade["ticker"],
        "side": trade["side"],
        "quantity": trade["quantity"],
        "price": trade["price"],
        "executed_at": trade["executed_at"],
    }


def _serialize_position(position: dict | None) -> dict | None:
    if position is None:
        return None
    return {
        "ticker": position["ticker"],
        "quantity": position["quantity"],
        "avg_cost": position["avg_cost"],
    }


@router.get("")
async def get_portfolio(price_cache=Depends(get_price_cache)) -> dict:
    """Current positions, cash, total value and unrealized P&L (§5.1)."""
    return portfolio_service.get_portfolio_state(price_cache)


@router.post("/trade")
async def execute_trade(
    body: TradeRequest,
    price_cache=Depends(get_price_cache),
) -> dict:
    """Execute a market order. 400 with ``{"detail": ...}`` on validation failure (§5.2)."""
    result = portfolio_service.execute_trade(
        ticker=body.ticker,
        side=body.side,
        quantity=body.quantity,
        price_cache=price_cache,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return {
        "success": True,
        "error": None,
        "trade": _serialize_trade(result.trade),
        "position": _serialize_position(result.position),
        "cash_balance": result.cash_balance,
    }


@router.get("/history")
async def get_history() -> dict:
    """Portfolio value snapshots over time, oldest→newest (§5.3)."""
    snapshots = portfolio_service.get_history()
    return {
        "snapshots": [
            {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
            for s in snapshots
        ]
    }
