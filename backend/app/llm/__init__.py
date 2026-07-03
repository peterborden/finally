"""LLM integration package for FinAlly.

Public surface:
- ``LLMResponse`` / ``TradeInstruction`` / ``WatchlistChange`` — structured-output schema (PLAN §6/§9).
- ``parse_llm_response`` — tolerant parser (valid + malformed graceful handling).
- ``generate_response`` — the entry point the chat endpoint calls (mock or real Cerebras call).
- ``build_messages`` / ``SYSTEM_PROMPT`` — prompt assembly (PLAN §9).
- ``mock_response`` — deterministic mock for ``LLM_MOCK=true``.
"""

from .client import generate_response
from .mock import mock_response
from .prompt import SYSTEM_PROMPT, build_messages, build_watchlist_context
from .schema import (
    LLMResponse,
    TradeInstruction,
    WatchlistChange,
    parse_llm_response,
)

__all__ = [
    "LLMResponse",
    "TradeInstruction",
    "WatchlistChange",
    "parse_llm_response",
    "generate_response",
    "mock_response",
    "build_messages",
    "build_watchlist_context",
    "SYSTEM_PROMPT",
]
