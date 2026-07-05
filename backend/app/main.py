"""FastAPI application factory for FinAlly.

Wires together the market data subsystem (app.market), the SQLite
persistence layer (app.db), the health endpoint, and static serving of the
exported frontend. Exposes a module-level `app` so `uvicorn app.main:app`
and `python -m app` both work.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .db import get_db_path, init_database
from .market import PriceCache, create_market_data_source, create_stream_router
from .market.seed_prices import SEED_PRICES
from .portfolio import create_portfolio_router
from .snapshots import SnapshotRecorder
from .watchlist import create_watchlist_router

logger = logging.getLogger(__name__)


def _resolve_frontend_dir() -> Path:
    """Resolve the static frontend directory from FRONTEND_DIST or the default.

    Default: backend/app/static (placeholder page until the Phase 4 Next.js
    export replaces it).
    """
    env_dir = os.environ.get("FRONTEND_DIST")
    return Path(env_dir) if env_dir else Path(__file__).parent / "static"


def _build_lifespan(cache: PriceCache):  # type: ignore[no-untyped-def]
    """Create the lifespan context manager bound to a specific PriceCache.

    The cache must be created before the SSE router is mounted (route
    registration happens at create_app() time, before startup), so the same
    instance is threaded through both the router and the lifespan closure.
    """

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Start the market data source on startup; stop it on shutdown.

        A source failure is logged rather than left to crash the app, so a
        transient market data issue does not prevent the API/static/DB parts
        of the app from serving.
        """
        app.state.market_source = None
        app.state.snapshot_task = None

        source = create_market_data_source(cache)
        try:
            await source.start(list(SEED_PRICES.keys()))
            app.state.market_source = source
        except Exception:
            logger.exception(
                "Market data source failed to start; continuing without live prices"
            )

        try:
            recorder = SnapshotRecorder()
            recorder.start(cache)
            app.state.snapshot_task = recorder
        except Exception:
            logger.exception(
                "Portfolio snapshotter failed to start; continuing without periodic snapshots"
            )

        try:
            yield
        finally:
            if app.state.snapshot_task is not None:
                try:
                    await app.state.snapshot_task.stop()
                except Exception:
                    logger.exception("Portfolio snapshotter failed to stop cleanly")
            if app.state.market_source is not None:
                try:
                    await app.state.market_source.stop()
                except Exception:
                    logger.exception("Market data source failed to stop cleanly")

    return lifespan


def create_app() -> FastAPI:
    """Build and configure the FinAlly FastAPI application."""
    cache = PriceCache()
    app = FastAPI(title="FinAlly", lifespan=_build_lifespan(cache))
    app.state.price_cache = cache

    # --- API routes (registered before the static mount so /api/* wins) ---

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Health check suitable for a Docker healthcheck."""
        return {"status": "ok"}

    @app.middleware("http")
    async def ensure_database(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Lazily create + seed the SQLite database on the first request.

        Guarded by an app.state flag so init_database (idempotent but not
        free) only runs its full check once per process.
        """
        if not getattr(request.app.state, "_db_initialized", False):
            init_database(get_db_path())
            request.app.state._db_initialized = True
        return await call_next(request)

    app.include_router(create_stream_router(cache))
    app.include_router(create_watchlist_router())
    app.include_router(create_portfolio_router())

    # --- Static frontend (mounted LAST so it never shadows /api/*) ---

    frontend_dir = _resolve_frontend_dir()
    frontend_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

    return app


app = create_app()
