"""Tests for the deterministic mock LLM intent parser."""

from __future__ import annotations

from app.llm.mock import mock_response


class TestTradeIntents:
    def test_buy_ticker(self):
        r = mock_response("buy 5 AAPL")
        assert len(r.trades) == 1
        assert r.trades[0].ticker == "AAPL"
        assert r.trades[0].side == "buy"
        assert r.trades[0].quantity == 5
        assert "AAPL" in r.message

    def test_buy_shares_of(self):
        r = mock_response("Please buy 10 shares of MSFT")
        assert r.trades[0].ticker == "MSFT"
        assert r.trades[0].quantity == 10

    def test_sell_ticker(self):
        r = mock_response("sell 3 TSLA now")
        assert r.trades[0].side == "sell"
        assert r.trades[0].ticker == "TSLA"
        assert r.trades[0].quantity == 3

    def test_company_name_resolves_to_ticker(self):
        r = mock_response("buy 5 shares of Apple")
        assert r.trades[0].ticker == "AAPL"

    def test_fractional_quantity(self):
        r = mock_response("buy 2.5 NVDA")
        assert r.trades[0].quantity == 2.5

    def test_deterministic(self):
        a = mock_response("buy 5 AAPL")
        b = mock_response("buy 5 AAPL")
        assert a.model_dump() == b.model_dump()


class TestWatchlistIntents:
    def test_add_ticker(self):
        r = mock_response("add PYPL to watchlist")
        assert len(r.watchlist_changes) == 1
        assert r.watchlist_changes[0].ticker == "PYPL"
        assert r.watchlist_changes[0].action == "add"
        assert "PYPL" in r.message

    def test_watch_verb(self):
        r = mock_response("watch AMD please")
        assert r.watchlist_changes[0].ticker == "AMD"
        assert r.watchlist_changes[0].action == "add"

    def test_remove_ticker(self):
        r = mock_response("remove NFLX from watchlist")
        assert r.watchlist_changes[0].ticker == "NFLX"
        assert r.watchlist_changes[0].action == "remove"

    def test_unwatch_verb(self):
        r = mock_response("unwatch V")
        assert r.watchlist_changes[0].ticker == "V"
        assert r.watchlist_changes[0].action == "remove"

    def test_watchlist_word_not_mistaken_for_ticker(self):
        r = mock_response("show me my watchlist")
        assert r.watchlist_changes == []


class TestNoIntent:
    def test_plain_question_no_actions(self):
        r = mock_response("How is my portfolio doing?")
        assert r.trades == []
        assert r.watchlist_changes == []
        assert isinstance(r.message, str) and r.message

    def test_empty_message(self):
        r = mock_response("")
        assert r.trades == []
        assert r.watchlist_changes == []
        assert r.message
