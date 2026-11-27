"""Tests for the portfolio router (§5.1–5.3)."""

from __future__ import annotations


def test_get_portfolio_empty(client):
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions_value"] == 0.0
    assert body["total_value"] == 10000.0
    assert body["positions"] == []


def test_trade_buy_success_shape(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["trade"] == {
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 10,
        "price": 190.0,
        "executed_at": body["trade"]["executed_at"],
    }
    assert body["position"] == {"ticker": "AAPL", "quantity": 10, "avg_cost": 190.0}
    assert body["cash_balance"] == 8100.0


def test_trade_then_portfolio_reflects_position(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    body = client.get("/api/portfolio").json()
    assert body["cash_balance"] == 8100.0
    assert body["positions_value"] == 1900.0
    assert body["total_value"] == 10000.0
    assert len(body["positions"]) == 1
    assert body["positions"][0]["ticker"] == "AAPL"


def test_trade_insufficient_cash_returns_400_detail(client):
    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1000, "side": "buy"},
    )
    assert resp.status_code == 400
    assert "Insufficient cash" in resp.json()["detail"]


def test_trade_no_price_returns_400(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "TSLA", "quantity": 1, "side": "buy"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No price available for TSLA"


def test_trade_bad_quantity_returns_400(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0, "side": "buy"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Quantity must be positive"


def test_trade_missing_field_returns_422(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy"})
    assert resp.status_code == 422


def test_history_empty(client):
    resp = client.get("/api/portfolio/history")
    assert resp.status_code == 200
    assert resp.json() == {"snapshots": []}


def test_history_after_trade_has_snapshot(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})
    body = client.get("/api/portfolio/history").json()
    assert len(body["snapshots"]) == 1
    snap = body["snapshots"][0]
    assert set(snap) == {"total_value", "recorded_at"}
    assert snap["total_value"] == 10000.0
