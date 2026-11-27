"""Tests for the client dispatch (mock vs real) and graceful fallback.

No real network calls: the real path is exercised by monkeypatching litellm.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import app.llm.client as client
from app.llm.schema import LLMResponse


class TestMockDispatch:
    def test_mock_mode_uses_mock_response(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        r = client.generate_response("buy 5 AAPL")
        assert isinstance(r, LLMResponse)
        assert r.trades[0].ticker == "AAPL"

    def test_is_mock_enabled_truthy_values(self, monkeypatch):
        for val in ("true", "True", "1", "yes", "on"):
            monkeypatch.setenv("LLM_MOCK", val)
            assert client.is_mock_enabled() is True
        for val in ("false", "0", "", "no"):
            monkeypatch.setenv("LLM_MOCK", val)
            assert client.is_mock_enabled() is False


class TestRealPath:
    def test_successful_structured_call(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        payload = json.dumps(
            {
                "message": "Bought 5 AAPL.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}],
                "watchlist_changes": [],
            }
        )

        def fake_completion(**kwargs):
            # Structured output requested and provider pinned to cerebras.
            assert kwargs["model"] == client.MODEL
            assert kwargs["extra_body"] == client.EXTRA_BODY
            assert kwargs["response_format"] is LLMResponse
            msg = SimpleNamespace(content=payload)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

        monkeypatch.setattr("litellm.completion", fake_completion)
        r = client.generate_response("buy 5 AAPL", portfolio_state={"cash_balance": 10000})
        assert r.message == "Bought 5 AAPL."
        assert r.trades[0].ticker == "AAPL"

    def test_exception_falls_back_safely(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")

        def boom(**kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr("litellm.completion", boom)
        r = client.generate_response("buy 5 AAPL")
        assert isinstance(r, LLMResponse)
        assert r.trades == []
        assert r.watchlist_changes == []
        assert "trouble" in r.message.lower()
