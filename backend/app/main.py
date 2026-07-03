"""FastAPI application factory and lifespan wiring.

Owns the app-wide singletons: the ``PriceCache`` and ``MarketDataSource`` live
on ``app.state``; the market-data background task and the portfolio-snapshot
loop start in the lifespan and stop on shutdown. The built frontend is mounted
as an SPA fallback AFTER all ``/api`` routes.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.market import create_market_data_source, create_stream_router
from app.market.cache import PriceCache
from app.services import portfolio as portfolio_service

logger = logging.getLogger(__name__)

# backend/static/  (this file is backend/app/main.py)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _initial_tickers(settings) -> list[str]:
    """Tickers to start the market source with: the persisted watchlist if the
    DB layer is available, otherwise the configured defaults."""
    try:
        from app import db

        db.init_db()
        with db.connection() as conn:
            tickers = [row["ticker"] for row in db.get_watchlist(conn)]
        if tickers:
            return tickers
    except ImportError:
        logger.warning("app.db not available (parallel worktree) — using default tickers")
    except Exception:
        logger.exception("DB init/watchlist load failed — using default tickers")
    return list(settings.default_tickers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start market data + snapshot loop on startup; tear down on shutdown."""
    settings = get_settings()

    # Reuse the cache created in create_app() so the SSE router, the data source,
    # and the portfolio services all read/write ONE shared PriceCache.
    price_cache = app.state.price_cache
    source = create_market_data_source(price_cache)
    app.state.market_source = source

    tickers = _initial_tickers(settings)
    await source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    snapshot_task = asyncio.create_task(portfolio_service.snapshot_loop(price_cache))
    app.state.snapshot_task = snapshot_task

    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass
        await source.stop()
        logger.info("Market data source stopped")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="FinAlly", version="0.1.0", lifespan=lifespan)

    # A PriceCache is needed to build the SSE router at import/registration time.
    # The lifespan replaces app.state.price_cache with the running instance; the
    # SSE router closes over this same object, so we create it once here and
    # reuse it in the lifespan for a single shared cache.
    price_cache = PriceCache()
    app.state.price_cache = price_cache

    # --- API routers (registered BEFORE static mount) ---
    from app.api.health import router as health_router
    from app.api.portfolio import router as portfolio_router
    from app.api.watchlist import router as watchlist_router

    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(watchlist_router)
    app.include_router(create_stream_router(price_cache))

    # LLM chat router is built in a parallel worktree; register if present.
    try:
        from app.api.chat import router as chat_router

        app.include_router(chat_router)
        logger.info("Chat router registered")
    except ImportError:
        logger.warning("app.api.chat not available (parallel worktree) — /api/chat disabled")

    # --- Static frontend (SPA fallback) mounted LAST ---
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
        logger.info("Serving static frontend from %s", STATIC_DIR)
    else:
        logger.warning("Static dir %s absent — frontend not served", STATIC_DIR)

        @app.get("/")
        async def _placeholder() -> dict:
            return {"status": "backend running", "frontend": "not built"}

    return app


app = create_app()
