"""TestClient tests for the portfolio and trading API (PORT-01..06).

Reuses the db_path/client fixture pattern from test_main.py and
test_watchlist.py: FINALLY_DB_PATH is monkeypatched to an isolated tmp
file, and the app runs under `with TestClient(app)` so the lifespan starts
the simulator and populates app.state.market_source.

Each trade test seeds a deterministic fill price into the cache via
`client.app.state.price_cache.update(ticker, price)` so trades have a
stable, test-controlled price independent of the running simulator.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class TestPortfolio:
    """Integration tests for the /api/portfolio endpoints."""

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

    def test_get_portfolio_fresh_db(self, client):
        """GET /api/portfolio on a fresh DB: $10k cash, no positions (PORT-01)."""
        response = client.get("/api/portfolio")
        assert response.status_code == 200
        body = response.json()
        assert body["cash_balance"] == 10000.0
        assert body["positions"] == []
        assert body["total_value"] == 10000.0
        assert body["total_unrealized_pnl"] == 0

    def test_buy_fills_at_cached_price_and_updates_cash(self, client):
        """Buy 10 AAPL @ 100: cash decreases by 1000, position appears (PORT-02, PORT-04)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["filled_quantity"] == 10
        assert body["filled_price"] == 100.0
        assert body["portfolio"]["cash_balance"] == 9000.0

        get_response = client.get("/api/portfolio")
        get_body = get_response.json()
        assert get_body["cash_balance"] == 9000.0
        assert len(get_body["positions"]) == 1
        position = get_body["positions"][0]
        assert position["ticker"] == "AAPL"
        assert position["quantity"] == 10
        assert position["avg_cost"] == 100.0
        # total_value == cash (9000) + 10 shares * 100 == 10000, at the seeded price
        assert get_body["total_value"] == 10000.0

        # A trade row was recorded.
        history_response = client.get("/api/portfolio/history")
        assert history_response.status_code == 200
        assert len(history_response.json()) >= 1

    def test_second_buy_computes_weighted_average_cost(self, client):
        """Buying again at a different price updates the weighted avg_cost (PORT-04)."""
        client.app.state.price_cache.update("AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

        client.app.state.price_cache.update("AAPL", 200.0)
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
        )
        assert response.status_code == 200

        get_body = client.get("/api/portfolio").json()
        position = get_body["positions"][0]
        assert position["quantity"] == 20
        assert position["avg_cost"] == 150.0

    def test_fractional_buy_updates_cash_and_position_exactly(self, client):
        """A fractional share quantity (2.5) updates cash and position with exact math."""
        client.app.state.price_cache.update("AAPL", 100.0)

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 2.5}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["portfolio"]["cash_balance"] == pytest.approx(9750.0)

        get_body = client.get("/api/portfolio").json()
        position = get_body["positions"][0]
        assert position["quantity"] == pytest.approx(2.5)
        assert position["avg_cost"] == pytest.approx(100.0)

    def test_sell_all_shares_removes_position_and_increases_cash(self, client):
        """Selling the full held quantity removes the position row (PORT-02)."""
        client.app.state.price_cache.update("AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10})

        client.app.state.price_cache.update("AAPL", 120.0)
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 10}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["portfolio"]["cash_balance"] == pytest.approx(9000.0 + 1200.0)
        assert body["portfolio"]["positions"] == []

        get_body = client.get("/api/portfolio").json()
        assert get_body["positions"] == []

    def test_buy_insufficient_cash_rejected_and_unchanged(self, client):
        """A buy costing more than available cash returns 400 with no state change (PORT-03)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        before = client.get("/api/portfolio").json()

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1000}
        )
        assert response.status_code == 400
        assert "detail" in response.json()
        assert response.json()["detail"]

        after = client.get("/api/portfolio").json()
        assert after == before

    def test_sell_insufficient_shares_rejected_and_unchanged(self, client):
        """Selling more shares than held (or with no position) returns 400, unchanged (PORT-03)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        before = client.get("/api/portfolio").json()

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 5}
        )
        assert response.status_code == 400
        assert response.json()["detail"]

        after = client.get("/api/portfolio").json()
        assert after == before

    def test_sell_more_than_held_after_partial_position_rejected_and_unchanged(self, client):
        """Selling more than a held (smaller) position is rejected with no state change."""
        client.app.state.price_cache.update("AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})

        before = client.get("/api/portfolio").json()

        response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 10}
        )
        assert response.status_code == 400

        after = client.get("/api/portfolio").json()
        assert after == before

    def test_non_positive_quantity_rejected_by_pydantic(self, client):
        """quantity <= 0 in the request body is rejected (422 Pydantic validation)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        zero_response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 0}
        )
        assert zero_response.status_code == 422

        negative_response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": -5}
        )
        assert negative_response.status_code == 422

    def test_trade_with_no_cached_price_rejected(self, client):
        """A ticker with no cached price is rejected with 400, not a crash."""
        response = client.post(
            "/api/portfolio/trade", json={"ticker": "ZZZZ", "side": "buy", "quantity": 1}
        )
        assert response.status_code == 400

    def test_immediate_snapshot_recorded_after_successful_trade(self, client):
        """Every successful trade writes an immediate snapshot row (PORT-06)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        trade_response = client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10}
        )
        post_trade_total = trade_response.json()["portfolio"]["total_value"]

        history_response = client.get("/api/portfolio/history")
        assert history_response.status_code == 200
        snapshots = history_response.json()
        assert len(snapshots) >= 1
        assert any(s["total_value"] == pytest.approx(post_trade_total) for s in snapshots)

    def test_history_ordered_by_recorded_at(self, client):
        """GET /api/portfolio/history returns snapshots ordered by recorded_at (PORT-05)."""
        client.app.state.price_cache.update("AAPL", 100.0)
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})

        response = client.get("/api/portfolio/history")
        assert response.status_code == 200
        snapshots = response.json()
        assert len(snapshots) >= 2
        recorded_ats = [s["recorded_at"] for s in snapshots]
        assert recorded_ats == sorted(recorded_ats)
