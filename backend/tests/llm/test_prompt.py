"""Tests for prompt assembly and context rendering."""

from __future__ import annotations

from types import SimpleNamespace

from app.llm.prompt import (
    SYSTEM_PROMPT,
    build_context_block,
    build_messages,
    build_watchlist_context,
)


class FakeCache:
    def __init__(self, prices: dict | None = None):
        self._prices = prices or {}

    def get(self, ticker):
        return self._prices.get(ticker)


def _update(price, change_percent, direction):
    return SimpleNamespace(price=price, change_percent=change_percent, direction=direction)


PORTFOLIO = {
    "cash_balance": 8075.0,
    "positions_value": 1925.0,
    "total_value": 10000.0,
    "total_unrealized_pnl": 25.0,
    "positions": [
        {
            "ticker": "AAPL",
            "quantity": 10,
            "avg_cost": 190.0,
            "current_price": 192.5,
            "unrealized_pnl": 25.0,
            "unrealized_pnl_percent": 1.32,
        }
    ],
}


class TestWatchlistContext:
    def test_combines_rows_with_live_prices(self):
        cache = FakeCache({"AAPL": _update(192.5, 0.78, "up")})
        rows = [{"ticker": "AAPL"}, {"ticker": "TSLA"}]
        ctx = build_watchlist_context(rows, cache)
        assert ctx[0] == {
            "ticker": "AAPL",
            "price": 192.5,
            "change_percent": 0.78,
            "direction": "up",
        }
        # No price yet for TSLA -> null price fields.
        assert ctx[1]["ticker"] == "TSLA"
        assert ctx[1]["price"] is None

    def test_empty_and_none(self):
        assert build_watchlist_context([], FakeCache()) == []
        assert build_watchlist_context(None, FakeCache()) == []

    def test_tolerates_none_cache(self):
        ctx = build_watchlist_context([{"ticker": "AAPL"}], None)
        assert ctx[0]["price"] is None


class TestContextBlock:
    def test_renders_numbers(self):
        block = build_context_block(PORTFOLIO, build_watchlist_context([{"ticker": "AAPL"}], FakeCache()))
        assert "AAPL" in block
        assert "$8,075.00" in block
        assert "PORTFOLIO" in block

    def test_handles_missing_portfolio(self):
        block = build_context_block(None, [])
        assert "unavailable" in block.lower()


class TestBuildMessages:
    def test_structure_and_order(self):
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        msgs = build_messages("buy 5 AAPL", PORTFOLIO, [], history)
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == SYSTEM_PROMPT
        assert msgs[1]["role"] == "system"  # context block
        assert msgs[2] == {"role": "user", "content": "hi"}
        assert msgs[3] == {"role": "assistant", "content": "hello"}
        assert msgs[-1] == {"role": "user", "content": "buy 5 AAPL"}

    def test_filters_bad_history_rows(self):
        history = [
            {"role": "system", "content": "should be dropped"},
            {"role": "user", "content": None},
            {"role": "user", "content": "keep me"},
        ]
        msgs = build_messages("q", None, None, history)
        contents = [m["content"] for m in msgs]
        assert "should be dropped" not in contents
        assert "keep me" in contents
