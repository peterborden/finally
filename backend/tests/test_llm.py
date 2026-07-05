"""Unit tests for app.llm (CHAT-02, CHAT-07).

Pure function tests -- no TestClient, no DB, no FastAPI. The mock-path
tests patch `litellm.completion` to raise if called at all, proving the
mock branch performs zero network I/O. The real-path test patches
`litellm.completion` with a stub and asserts both the parsed return value
and the exact call arguments (model/response_format/extra_body), so it is
provably offline while still exercising the real call-construction code.
"""

from __future__ import annotations

import pytest

from app.llm import (
    EXTRA_BODY,
    MODEL,
    ChatResponse,
    TradeIntent,
    WatchlistChange,
    build_messages,
    generate_chat_response,
    is_mock_enabled,
)


def _raise_if_called(*_args, **_kwargs):
    raise AssertionError("litellm.completion must not be called in mock mode")


class TestChatResponseSchema:
    """ChatResponse.model_validate_json parses the structured-output shape."""

    def test_message_only_defaults_to_empty_action_lists(self):
        response = ChatResponse.model_validate_json('{"message":"hi"}')
        assert response.message == "hi"
        assert response.trades == []
        assert response.watchlist_changes == []

    def test_nested_trades_and_watchlist_changes_parse(self):
        payload = (
            '{"message":"done",'
            '"trades":[{"ticker":"AAPL","side":"buy","quantity":10}],'
            '"watchlist_changes":[{"ticker":"PYPL","action":"add"}]}'
        )
        response = ChatResponse.model_validate_json(payload)
        assert response.message == "done"
        assert response.trades == [TradeIntent(ticker="AAPL", side="buy", quantity=10.0)]
        assert response.watchlist_changes == [WatchlistChange(ticker="PYPL", action="add")]


class TestIsMockEnabled:
    """is_mock_enabled() reads LLM_MOCK case-insensitively."""

    @pytest.mark.parametrize("value", ["true", "TRUE", "True"])
    def test_true_values(self, monkeypatch, value):
        monkeypatch.setenv("LLM_MOCK", value)
        assert is_mock_enabled() is True

    def test_false_when_explicitly_false(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        assert is_mock_enabled() is False

    def test_false_when_unset(self, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        assert is_mock_enabled() is False


class TestMockPath:
    """generate_chat_response() under LLM_MOCK=true: deterministic, offline."""

    @pytest.fixture(autouse=True)
    def _mock_env_and_no_network(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        monkeypatch.setattr("litellm.completion", _raise_if_called)

    def test_buy_directive_yields_one_trade_intent(self):
        response = generate_chat_response("ctx", [], "analyse [[buy:AAPL:10]]")
        assert response.trades == [TradeIntent(ticker="AAPL", side="buy", quantity=10.0)]
        assert response.watchlist_changes == []
        assert response.message

    def test_sell_directive_yields_one_sell_trade_intent(self):
        response = generate_chat_response("ctx", [], "[[sell:TSLA:2.5]]")
        assert response.trades == [TradeIntent(ticker="TSLA", side="sell", quantity=2.5)]

    def test_watch_add_directive_yields_one_watchlist_change(self):
        response = generate_chat_response("ctx", [], "please [[watch-add:PYPL]]")
        assert response.watchlist_changes == [WatchlistChange(ticker="PYPL", action="add")]
        assert response.trades == []

    def test_watch_remove_directive_yields_remove_action(self):
        response = generate_chat_response("ctx", [], "[[watch-remove:AAPL]]")
        assert response.watchlist_changes == [WatchlistChange(ticker="AAPL", action="remove")]

    def test_plain_message_yields_non_empty_message_and_no_actions(self):
        response = generate_chat_response("ctx", [], "what do you think of my portfolio?")
        assert response.message
        assert response.trades == []
        assert response.watchlist_changes == []


class TestRealPath:
    """generate_chat_response() when LLM_MOCK is unset: calls litellm.completion."""

    class _StubMessage:
        def __init__(self, content: str) -> None:
            self.content = content

    class _StubChoice:
        def __init__(self, content: str) -> None:
            self.message = TestRealPath._StubMessage(content)

    class _StubResponse:
        def __init__(self, content: str) -> None:
            self.choices = [TestRealPath._StubChoice(content)]

    def test_calls_completion_with_expected_args_and_parses_result(self, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        captured: dict = {}

        def _stub_completion(*, model, messages, response_format, reasoning_effort, extra_body):
            captured["model"] = model
            captured["messages"] = messages
            captured["response_format"] = response_format
            captured["reasoning_effort"] = reasoning_effort
            captured["extra_body"] = extra_body
            return self._StubResponse('{"message":"stub reply"}')

        monkeypatch.setattr("litellm.completion", _stub_completion)

        response = generate_chat_response("portfolio ctx", [], "how am I doing?")

        assert response == ChatResponse(message="stub reply")
        assert captured["model"] == MODEL
        assert captured["response_format"] is ChatResponse
        assert captured["extra_body"] == EXTRA_BODY
        assert captured["reasoning_effort"] == "low"


class TestBuildMessages:
    """build_messages() orders system, history, then the new user message."""

    def test_system_first_history_preserved_user_last(self):
        history = [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
        ]
        messages = build_messages("PORTFOLIO_CONTEXT_TEXT", history, "new question")

        assert messages[0]["role"] == "system"
        assert "PORTFOLIO_CONTEXT_TEXT" in messages[0]["content"]
        assert messages[1:3] == history
        assert messages[-1] == {"role": "user", "content": "new question"}
