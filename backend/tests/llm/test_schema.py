"""Tests for the structured-output schema and tolerant parser."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.llm.schema import (
    LLMResponse,
    TradeInstruction,
    WatchlistChange,
    parse_llm_response,
)


class TestModels:
    def test_trade_normalizes_ticker_and_side(self):
        t = TradeInstruction(ticker="  aapl ", side="BUY", quantity=5)
        assert t.ticker == "AAPL"
        assert t.side == "buy"
        assert t.quantity == 5

    def test_watchlist_change_normalizes(self):
        c = WatchlistChange(ticker="pypl", action="ADD")
        assert c.ticker == "PYPL"
        assert c.action == "add"

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            TradeInstruction(ticker="AAPL", side="buy", quantity=0)

    def test_invalid_side_rejected(self):
        with pytest.raises(ValidationError):
            TradeInstruction(ticker="AAPL", side="hold", quantity=1)

    def test_defaults_empty_lists(self):
        r = LLMResponse(message="hi")
        assert r.trades == []
        assert r.watchlist_changes == []


class TestParseValid:
    def test_full_valid_json(self):
        raw = json.dumps(
            {
                "message": "Bought 5 AAPL.",
                "trades": [{"ticker": "aapl", "side": "buy", "quantity": 5}],
                "watchlist_changes": [{"ticker": "pypl", "action": "add"}],
            }
        )
        r = parse_llm_response(raw)
        assert r.message == "Bought 5 AAPL."
        assert r.trades[0].ticker == "AAPL"
        assert r.trades[0].side == "buy"
        assert r.watchlist_changes[0].action == "add"

    def test_message_only(self):
        r = parse_llm_response('{"message": "Your portfolio looks balanced."}')
        assert r.message == "Your portfolio looks balanced."
        assert r.trades == []


class TestParseMalformed:
    def test_not_json_returns_text_as_message(self):
        r = parse_llm_response("I can't help with that right now.")
        assert "can't help" in r.message
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_empty_and_none(self):
        for bad in ("", "   ", None):
            r = parse_llm_response(bad)
            assert isinstance(r.message, str) and r.message
            assert r.trades == []

    def test_lenient_drops_invalid_trade_items(self):
        raw = json.dumps(
            {
                "message": "Executing partial.",
                "trades": [
                    {"ticker": "AAPL", "side": "buy", "quantity": 5},
                    {"ticker": "TSLA", "side": "hold", "quantity": 2},  # invalid side
                    {"ticker": "MSFT", "side": "buy", "quantity": -1},  # invalid qty
                ],
                "watchlist_changes": [
                    {"ticker": "PYPL", "action": "add"},
                    {"ticker": "X", "action": "toggle"},  # invalid action
                ],
            }
        )
        r = parse_llm_response(raw)
        assert r.message == "Executing partial."
        assert [t.ticker for t in r.trades] == ["AAPL"]
        assert [c.ticker for c in r.watchlist_changes] == ["PYPL"]

    def test_lenient_missing_message_gets_fallback(self):
        r = parse_llm_response(json.dumps({"trades": []}))
        assert isinstance(r.message, str) and r.message

    def test_json_array_not_object_falls_back(self):
        r = parse_llm_response("[1, 2, 3]")
        assert isinstance(r.message, str) and r.message
        assert r.trades == []
