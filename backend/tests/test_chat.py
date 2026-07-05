"""TestClient tests for POST /api/chat under LLM_MOCK=true (CHAT-01, CHAT-04,
CHAT-05, CHAT-06, CHAT-07).

Reuses the db_path/client fixture pattern from test_portfolio.py and
test_watchlist.py: FINALLY_DB_PATH is monkeypatched to an isolated tmp
file, and the app runs under `with TestClient(app)` so the lifespan starts
the simulator. `LLM_MOCK=true` is set autouse for the whole module so no
test can reach OpenRouter -- `app.llm.generate_chat_response` dispatches to
the deterministic, offline mock-directive path documented in `app/llm.py`.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import create_app


class TestChat:
    """Integration tests for the /api/chat endpoint."""

    @pytest.fixture(autouse=True)
    def llm_mock(self, monkeypatch):
        """Force the deterministic mock LLM path for every test in this module."""
        monkeypatch.setenv("LLM_MOCK", "true")

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

    def test_structured_response_returned(self, client):
        """POST /api/chat returns a message string + an actions list (CHAT-01)."""
        response = client.post("/api/chat", json={"message": "hello"})
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["message"], str)
        assert body["message"]
        assert isinstance(body["actions"], list)
        assert body["actions"] == []

    def test_mock_buy_directive_executes_trade(self, client):
        """[[buy:AAPL:10]] auto-executes and updates the portfolio (CHAT-04)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        response = client.post("/api/chat", json={"message": "please [[buy:AAPL:10]] for me"})
        assert response.status_code == 200
        body = response.json()

        trade_actions = [a for a in body["actions"] if a["type"] == "trade"]
        assert len(trade_actions) == 1
        assert trade_actions[0]["status"] == "ok"
        assert trade_actions[0]["ticker"] == "AAPL"

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["cash_balance"] == 9000.0
        positions = {p["ticker"]: p for p in portfolio["positions"]}
        assert positions["AAPL"]["quantity"] == 10

    def test_mock_watch_add_directive_updates_watchlist(self, client):
        """[[watch-add:PYPL]] auto-applies and appears in the watchlist (CHAT-05)."""
        response = client.post("/api/chat", json={"message": "add PYPL [[watch-add:PYPL]]"})
        assert response.status_code == 200
        body = response.json()

        watchlist_actions = [a for a in body["actions"] if a["type"] == "watchlist"]
        assert len(watchlist_actions) == 1
        assert watchlist_actions[0]["status"] == "ok"
        assert watchlist_actions[0]["ticker"] == "PYPL"

        watchlist = client.get("/api/watchlist").json()
        tickers = {entry["ticker"] for entry in watchlist}
        assert "PYPL" in tickers

    def test_invalid_trade_surfaced_as_error_not_fatal(self, client):
        """A trade exceeding available cash returns 200 with an error action (CHAT-04)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        before = client.get("/api/portfolio").json()

        response = client.post(
            "/api/chat", json={"message": "go big: [[buy:AAPL:100000]]"}
        )
        assert response.status_code == 200
        body = response.json()

        trade_actions = [a for a in body["actions"] if a["type"] == "trade"]
        assert len(trade_actions) == 1
        assert trade_actions[0]["status"] == "error"
        assert "cash" in trade_actions[0]["detail"].lower()

        after = client.get("/api/portfolio").json()
        assert after == before

    def test_chat_messages_persisted_with_actions_json(self, client, db_path):
        """A user row (actions NULL) and an assistant row (actions JSON) persist (CHAT-06)."""
        client.app.state.price_cache.update("AAPL", 100.0)

        response = client.post("/api/chat", json={"message": "[[buy:AAPL:5]]"})
        assert response.status_code == 200
        expected_actions = response.json()["actions"]

        conn = get_connection(db_path)
        try:
            rows = conn.execute(
                "SELECT role, content, actions FROM chat_messages WHERE user_id = ? "
                "ORDER BY created_at",
                ("default",),
            ).fetchall()
        finally:
            conn.close()

        user_rows = [r for r in rows if r["role"] == "user"]
        assistant_rows = [r for r in rows if r["role"] == "assistant"]

        assert len(user_rows) == 1
        assert user_rows[0]["content"] == "[[buy:AAPL:5]]"
        assert user_rows[0]["actions"] is None

        assert len(assistant_rows) == 1
        persisted_actions = json.loads(assistant_rows[0]["actions"])
        assert persisted_actions == expected_actions
