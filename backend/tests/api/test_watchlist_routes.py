"""Tests for the watchlist router (§5.4–5.6)."""

from __future__ import annotations


def test_get_watchlist_empty(client):
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    assert resp.json() == {"watchlist": []}


def test_add_ticker_returns_201_and_item_shape(client, market_source):
    resp = client.post("/api/watchlist", json={"ticker": "aapl"})
    assert resp.status_code == 201
    item = resp.json()
    assert item["ticker"] == "AAPL"
    assert set(item) == {
        "ticker", "price", "previous_price", "change", "change_percent", "direction",
    }
    # AAPL has a seeded price in the fixture cache.
    assert item["price"] == 190.0
    market_source.add_ticker.assert_awaited_once_with("AAPL")


def test_add_then_get_watchlist(client):
    client.post("/api/watchlist", json={"ticker": "AAPL"})
    client.post("/api/watchlist", json={"ticker": "MSFT"})
    body = client.get("/api/watchlist").json()
    assert [i["ticker"] for i in body["watchlist"]] == ["AAPL", "MSFT"]


def test_add_ticker_no_price_yet_returns_nulls(client):
    resp = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert resp.status_code == 201
    item = resp.json()
    assert item["ticker"] == "PYPL"
    assert item["price"] is None
    assert item["direction"] is None


def test_remove_ticker_present(client, market_source):
    client.post("/api/watchlist", json={"ticker": "AAPL"})
    resp = client.delete("/api/watchlist/aapl")
    assert resp.status_code == 200
    assert resp.json() == {"removed": True}
    market_source.remove_ticker.assert_awaited_once_with("AAPL")


def test_remove_ticker_absent_returns_404(client):
    resp = client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404
    assert "ZZZZ" in resp.json()["detail"]


def test_add_ticker_missing_field_returns_422(client):
    resp = client.post("/api/watchlist", json={})
    assert resp.status_code == 422
