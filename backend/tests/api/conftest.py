"""Fixtures for API route tests.

Builds the real app via ``create_app()`` but does NOT run the lifespan (a plain
``TestClient(app)`` used without ``with`` skips startup/shutdown), so no
simulator or snapshot loop starts. App-state singletons are set directly and the
service DB layer is patched with an in-memory ``FakeDB``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import portfolio as portfolio_svc
from app.services import watchlist as watchlist_svc
from tests.services.fakes import FakeDB


@pytest.fixture
def fake_db() -> FakeDB:
    return FakeDB(cash=10000.0)


@pytest.fixture
def market_source() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(monkeypatch, fake_db, market_source) -> TestClient:
    monkeypatch.setattr(portfolio_svc, "db", fake_db)
    monkeypatch.setattr(watchlist_svc, "db", fake_db)

    app = create_app()
    cache = app.state.price_cache
    cache.update("AAPL", 190.0)
    cache.update("MSFT", 420.0)
    app.state.market_source = market_source

    # No `with` block => lifespan startup/shutdown is not run.
    return TestClient(app)
