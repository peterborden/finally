"""Shared FastAPI dependencies for accessing app.state singletons.

The ``PriceCache`` and ``MarketDataSource`` are created in ``main.py``'s
lifespan and stored on ``app.state``. Routers depend on these accessors rather
than reaching into globals, which keeps them testable (tests set ``app.state``
directly).
"""

from __future__ import annotations

from fastapi import Request


def get_price_cache(request: Request):
    """Return the shared PriceCache from app.state."""
    return request.app.state.price_cache


def get_market_source(request: Request):
    """Return the shared MarketDataSource from app.state."""
    return request.app.state.market_source
