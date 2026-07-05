"""TestClient tests for the watchlist API (WATCH-01/02/03).

Reuses the db_path/client fixture pattern from test_main.py: FINALLY_DB_PATH
is monkeypatched to an isolated tmp file, and the app runs under
`with TestClient(app)` so the lifespan starts the simulator and populates
app.state.market_source.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import create_app


class TestWatchlist:
    """Integration tests for the /api/watchlist endpoints."""

    @pytest.fixture
    def db_path(self, tmp_path, monkeypatch):
        """Point FINALLY_DB_PATH at an isolated tmp_path file for this test."""
        path = tmp_path / "finally.db"
        monkeypatch.setenv("FINALLY_DB_PATH", str(path))
        return path

    @pytest.fixture
    def client(self, db_path):
        """A TestClient with the lifespan run (starts/stops the market source)."""
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client

    def test_get_returns_default_tickers(self, client):
        """GET returns the 10 seeded default tickers (WATCH-01)."""
        response = client.get("/api/watchlist")
        assert response.status_code == 200
        entries = response.json()
        assert len(entries) == 10
        tickers = {entry["ticker"] for entry in entries}
        assert tickers == {
            "AAPL",
            "GOOGL",
            "MSFT",
            "AMZN",
            "TSLA",
            "NVDA",
            "META",
            "JPM",
            "V",
            "NFLX",
        }

    def test_get_reflects_seeded_cache_price(self, client, db_path):
        """After seeding a price into the cache, GET reflects it.

        A ticker inserted directly into the DB (bypassing the market source,
        so the simulator never seeds a cache entry for it) has no cache
        entry and returns price=None rather than raising.
        """
        client.app.state.price_cache.update("AAPL", 190.0)

        # Trigger lazy DB initialization (the schema is created on first
        # request, via middleware) before inserting directly.
        client.get("/api/health")

        conn = get_connection(db_path)
        try:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex, "default", "ZZZZ", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        response = client.get("/api/watchlist")
        assert response.status_code == 200
        entries = {entry["ticker"]: entry for entry in response.json()}

        assert entries["AAPL"]["price"] == 190.0
        assert entries["ZZZZ"]["price"] is None

    def test_post_new_ticker_normalizes_and_dedupes(self, client):
        """POST a lower-case ticker returns 201, normalizes, and is idempotent."""
        response = client.post("/api/watchlist", json={"ticker": "pypl"})
        assert response.status_code == 201
        assert response.json()["ticker"] == "PYPL"

        get_response = client.get("/api/watchlist")
        tickers = [entry["ticker"] for entry in get_response.json()]
        assert tickers.count("PYPL") == 1

        # Re-adding is a safe no-op (dedupe).
        second_response = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert second_response.status_code == 201

        get_response_again = client.get("/api/watchlist")
        tickers_again = [entry["ticker"] for entry in get_response_again.json()]
        assert tickers_again.count("PYPL") == 1

    def test_post_calls_market_source_add_ticker(self, client):
        """POST wires to the market source's add_ticker (WATCH-02)."""
        client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert "PYPL" in client.app.state.market_source.get_tickers()

    def test_delete_removes_ticker_and_is_idempotent(self, client):
        """DELETE returns 200, removes the ticker, and is idempotent (WATCH-03)."""
        response = client.delete("/api/watchlist/AAPL")
        assert response.status_code == 200
        assert response.json() == {"ticker": "AAPL", "removed": True}

        get_response = client.get("/api/watchlist")
        tickers = [entry["ticker"] for entry in get_response.json()]
        assert "AAPL" not in tickers

        # Deleting again is idempotent: still 200, removed=False.
        second_response = client.delete("/api/watchlist/AAPL")
        assert second_response.status_code == 200
        assert second_response.json() == {"ticker": "AAPL", "removed": False}

    def test_delete_calls_market_source_remove_ticker(self, client):
        """DELETE wires to the market source's remove_ticker (WATCH-03)."""
        client.delete("/api/watchlist/AAPL")
        assert "AAPL" not in client.app.state.market_source.get_tickers()
