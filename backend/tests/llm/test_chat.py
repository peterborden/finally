"""Tests for the POST /api/chat flow with all cross-module deps mocked.

Covers: trade success, trade failure -> errors, watchlist add/remove (incl.
remove-of-absent -> error), response reflecting only executed actions, and
persistence of user + assistant messages with the actions JSON.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.chat as chat_mod
from app.llm.schema import LLMResponse, TradeInstruction, WatchlistChange


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeCache:
    def get(self, ticker):
        return None

    def get_price(self, ticker):
        return None


def ok_trade(ticker, side, qty, price=100.0):
    return SimpleNamespace(
        success=True,
        error=None,
        trade={
            "ticker": ticker,
            "side": side,
            "quantity": qty,
            "price": price,
            "executed_at": "2026-01-01T00:00:00Z",
            "id": "trade-1",
        },
        position={"ticker": ticker, "quantity": qty, "avg_cost": price},
        cash_balance=1000.0,
    )


def fail_trade(error="Insufficient cash"):
    return SimpleNamespace(
        success=False, error=error, trade=None, position=None, cash_balance=1000.0
    )


class FakePortfolio:
    def __init__(self, state=None, results=None):
        self.state = state if state is not None else {"cash_balance": 1000.0, "positions": []}
        self.results = results or {}
        self.trade_calls = []

    def get_portfolio_state(self, price_cache):
        return self.state

    def execute_trade(self, ticker, side, quantity, price_cache):
        self.trade_calls.append((ticker, side, quantity))
        result = self.results.get(ticker)
        if result is None:
            return ok_trade(ticker, side, quantity)
        return result


class FakeWatchlist:
    def __init__(self, remove_returns=True):
        self.added = []
        self.removed = []
        self.remove_returns = remove_returns

    def add_ticker(self, ticker, source, price_cache):
        self.added.append(ticker)
        return {"ticker": ticker, "added_at": "2026-01-01T00:00:00Z"}

    def remove_ticker(self, ticker, source):
        self.removed.append(ticker)
        return self.remove_returns


class FakeDB:
    def __init__(self, history=None, watchlist=None):
        self.history = history or []
        self.watchlist = watchlist or []
        self.added_messages = []

    @contextmanager
    def connection(self):
        yield object()

    def get_recent_messages(self, conn, limit=20):
        return list(self.history)

    def get_watchlist(self, conn):
        return list(self.watchlist)

    def add_message(self, conn, role, content, actions=None):
        row = {"role": role, "content": content, "actions": actions}
        self.added_messages.append(row)
        return row


def make_client(llm_response, portfolio, watchlist, db):
    app = FastAPI()
    app.include_router(chat_mod.router)
    app.state.price_cache = FakeCache()
    app.state.market_source = object()

    def gen(user_message, portfolio_state=None, watchlist_context=None, history=None):
        return llm_response

    app.dependency_overrides[chat_mod.get_generate_fn] = lambda: gen
    app.dependency_overrides[chat_mod.get_portfolio_service] = lambda: portfolio
    app.dependency_overrides[chat_mod.get_watchlist_service] = lambda: watchlist
    app.dependency_overrides[chat_mod.get_db] = lambda: db
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_trade_success_reflected_and_persisted():
    llm = LLMResponse(
        message="Bought 5 AAPL.",
        trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=5)],
    )
    pf = FakePortfolio()
    wl = FakeWatchlist()
    db = FakeDB()
    client = make_client(llm, pf, wl, db)

    resp = client.post("/api/chat", json={"message": "buy 5 AAPL"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["message"] == "Bought 5 AAPL."
    assert body["errors"] == []
    assert len(body["trades"]) == 1
    # §5.7 trade shape — no leaked internal 'id' key.
    assert body["trades"][0] == {
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 5,
        "price": 100.0,
        "executed_at": "2026-01-01T00:00:00Z",
    }
    assert pf.trade_calls == [("AAPL", "buy", 5)]

    # Persistence: user then assistant, assistant carries actions JSON.
    assert [m["role"] for m in db.added_messages] == ["user", "assistant"]
    assert db.added_messages[0]["content"] == "buy 5 AAPL"
    assistant = db.added_messages[1]
    assert assistant["content"] == "Bought 5 AAPL."
    assert assistant["actions"]["trades"] == body["trades"]
    assert assistant["actions"]["errors"] == []


def test_trade_failure_goes_to_errors_not_trades():
    llm = LLMResponse(
        message="Trying to buy.",
        trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=999)],
    )
    pf = FakePortfolio(results={"AAPL": fail_trade("Insufficient cash: need $1000, have $10")})
    client = make_client(llm, pf, FakeWatchlist(), FakeDB())

    body = client.post("/api/chat", json={"message": "buy 999 AAPL"}).json()
    assert body["trades"] == []
    assert len(body["errors"]) == 1
    assert "AAPL" in body["errors"][0]
    assert "Insufficient cash" in body["errors"][0]


def test_mixed_trades_partial_success():
    llm = LLMResponse(
        message="Executing.",
        trades=[
            TradeInstruction(ticker="AAPL", side="buy", quantity=5),
            TradeInstruction(ticker="TSLA", side="buy", quantity=5),
        ],
    )
    pf = FakePortfolio(results={"TSLA": fail_trade("Insufficient cash")})
    body = make_client(llm, pf, FakeWatchlist(), FakeDB()).post(
        "/api/chat", json={"message": "buy some"}
    ).json()
    assert [t["ticker"] for t in body["trades"]] == ["AAPL"]
    assert len(body["errors"]) == 1
    assert "TSLA" in body["errors"][0]


def test_watchlist_add_and_remove_executed():
    llm = LLMResponse(
        message="Updated watchlist.",
        watchlist_changes=[
            WatchlistChange(ticker="PYPL", action="add"),
            WatchlistChange(ticker="NFLX", action="remove"),
        ],
    )
    wl = FakeWatchlist(remove_returns=True)
    body = make_client(llm, FakePortfolio(), wl, FakeDB()).post(
        "/api/chat", json={"message": "add pypl remove nflx"}
    ).json()

    assert wl.added == ["PYPL"]
    assert wl.removed == ["NFLX"]
    assert {"ticker": "PYPL", "action": "add"} in body["watchlist_changes"]
    assert {"ticker": "NFLX", "action": "remove"} in body["watchlist_changes"]
    assert body["errors"] == []


def test_watchlist_remove_absent_is_error():
    llm = LLMResponse(
        message="Removing.",
        watchlist_changes=[WatchlistChange(ticker="ZZZZ", action="remove")],
    )
    wl = FakeWatchlist(remove_returns=False)
    body = make_client(llm, FakePortfolio(), wl, FakeDB()).post(
        "/api/chat", json={"message": "remove zzzz"}
    ).json()
    assert body["watchlist_changes"] == []
    assert len(body["errors"]) == 1
    assert "ZZZZ" in body["errors"][0]


def test_no_actions_plain_message():
    llm = LLMResponse(message="Your portfolio is well diversified.")
    db = FakeDB()
    body = make_client(llm, FakePortfolio(), FakeWatchlist(), db).post(
        "/api/chat", json={"message": "how am I doing?"}
    ).json()
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert body["errors"] == []
    assert body["message"] == "Your portfolio is well diversified."
    assert len(db.added_messages) == 2


def test_empty_message_rejected():
    llm = LLMResponse(message="unused")
    client = make_client(llm, FakePortfolio(), FakeWatchlist(), FakeDB())
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/chat", json={}).status_code == 422


def test_context_loaded_from_db_and_portfolio():
    """Portfolio state + history are fetched and passed to the generator."""
    captured = {}

    llm = LLMResponse(message="ok")
    pf = FakePortfolio(state={"cash_balance": 4242.0, "positions": []})
    db = FakeDB(
        history=[{"role": "user", "content": "earlier"}],
        watchlist=[{"ticker": "AAPL"}],
    )

    app = FastAPI()
    app.include_router(chat_mod.router)
    app.state.price_cache = FakeCache()
    app.state.market_source = object()

    def gen(user_message, portfolio_state=None, watchlist_context=None, history=None):
        captured["portfolio_state"] = portfolio_state
        captured["watchlist_context"] = watchlist_context
        captured["history"] = history
        return llm

    app.dependency_overrides[chat_mod.get_generate_fn] = lambda: gen
    app.dependency_overrides[chat_mod.get_portfolio_service] = lambda: pf
    app.dependency_overrides[chat_mod.get_watchlist_service] = lambda: FakeWatchlist()
    app.dependency_overrides[chat_mod.get_db] = lambda: db

    TestClient(app).post("/api/chat", json={"message": "hello"})
    assert captured["portfolio_state"]["cash_balance"] == 4242.0
    assert captured["history"] == [{"role": "user", "content": "earlier"}]
    assert captured["watchlist_context"][0]["ticker"] == "AAPL"


def test_db_failure_does_not_500():
    """A DB read/write failure degrades gracefully; the chat still responds."""

    class BrokenDB(FakeDB):
        @contextmanager
        def connection(self):
            raise RuntimeError("db unavailable")
            yield  # pragma: no cover

    llm = LLMResponse(message="still here")
    resp = make_client(llm, FakePortfolio(), FakeWatchlist(), BrokenDB()).post(
        "/api/chat", json={"message": "hi"}
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "still here"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
