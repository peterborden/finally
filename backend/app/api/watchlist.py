"""Watchlist router: list / add / remove tickers (§5.4–5.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services import watchlist as watchlist_service

from .deps import get_market_source, get_price_cache

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str = Field(..., min_length=1)


@router.get("")
async def get_watchlist(price_cache=Depends(get_price_cache)) -> dict:
    """Current watchlist tickers with latest prices (§5.4)."""
    return {"watchlist": watchlist_service.get_watchlist(price_cache)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_ticker(
    body: AddTickerRequest,
    price_cache=Depends(get_price_cache),
    source=Depends(get_market_source),
) -> dict:
    """Add a ticker to the watchlist (§5.5). Returns the §5.4 per-item shape."""
    await watchlist_service.add_ticker(body.ticker, source, price_cache)
    return watchlist_service.watchlist_item(body.ticker.strip().upper(), price_cache)


@router.delete("/{ticker}")
async def remove_ticker(
    ticker: str,
    source=Depends(get_market_source),
) -> dict:
    """Remove a ticker from the watchlist (§5.6). 404 if it was not present."""
    removed = await watchlist_service.remove_ticker(ticker, source)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker {ticker.strip().upper()} not in watchlist",
        )
    return {"removed": True}
