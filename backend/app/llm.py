"""LLM chat wrapper: structured-output schema, prompt builder, Cerebras call.

Isolates the LLM concern (schema + prompt + call + mock switch) from the
HTTP/DB/auto-execution concern in `app.chat` (Phase 3 plan 03-03). This
module never imports FastAPI, sqlite3, or `app.portfolio` -- it is a pure,
unit-testable transport layer with a single public entry point,
`generate_chat_response()`.

Two call paths, selected by `is_mock_enabled()`:

- **Real path** (`LLM_MOCK` unset or not "true"): calls `litellm.completion`
  via OpenRouter with Cerebras as the inference provider, per the
  `cerebras-inference` skill (`.claude/skills/cerebras/SKILL.md`). Uses
  Structured Outputs (`response_format=ChatResponse`) so the model's JSON
  reply parses directly into the typed schema.
- **Mock path** (`LLM_MOCK=true`): deterministic, offline, no network call.
  Used by tests and the Phase 5 Playwright E2E suite so trades and
  watchlist changes can be driven without an OpenRouter key.

## Mock directive grammar

The mock path scans the incoming user message for stable, documented
directive tokens and turns them into the same typed actions a real LLM
response would produce:

- `[[buy:TICKER:QTY]]` -> `TradeIntent(ticker=TICKER, side="buy", quantity=QTY)`
- `[[sell:TICKER:QTY]]` -> `TradeIntent(ticker=TICKER, side="sell", quantity=QTY)`
- `[[watch-add:TICKER]]` -> `WatchlistChange(ticker=TICKER, action="add")`
- `[[watch-remove:TICKER]]` -> `WatchlistChange(ticker=TICKER, action="remove")`

`TICKER` is upper-cased; `QTY` is parsed as a float. A message with no
recognized directive yields an empty `trades`/`watchlist_changes` and a
short deterministic acknowledgement message.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

__all__ = [
    "TradeIntent",
    "WatchlistChange",
    "ChatResponse",
    "SYSTEM_PROMPT",
    "MODEL",
    "EXTRA_BODY",
    "build_messages",
    "is_mock_enabled",
    "generate_chat_response",
]

# Model + provider routing, per the cerebras-inference skill: LiteLLM ->
# OpenRouter -> Cerebras as the inference provider.
MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant embedded in a simulated "
    "trading workstation. Analyze the user's portfolio composition, risk "
    "concentration, and unrealized P&L using the portfolio context "
    "provided below. Suggest trades with clear reasoning, and execute "
    "trades when the user asks for one or agrees to one you proposed. "
    "Proactively manage the watchlist on the user's behalf when it makes "
    "sense. Be concise and data-driven. Always respond with valid "
    "structured JSON matching the required schema."
)

# Directive grammar for the deterministic mock path -- see module docstring.
_BUY_SELL_RE = re.compile(r"\[\[(buy|sell):([A-Za-z.]+):([0-9]*\.?[0-9]+)\]\]")
_WATCH_RE = re.compile(r"\[\[watch-(add|remove):([A-Za-z.]+)\]\]")


class TradeIntent(BaseModel):
    """A single trade the LLM wants auto-executed."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    """A single watchlist add/remove the LLM wants applied."""

    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """Structured output schema for the chat LLM call (PLAN.md Section 9).

    `trades` and `watchlist_changes` default to empty lists so a
    message-only reply (no actions) parses without either key present.
    """

    message: str
    trades: list[TradeIntent] = []
    watchlist_changes: list[WatchlistChange] = []


def build_messages(
    portfolio_context: str, history: list[dict[str, str]], user_message: str
) -> list[dict[str, str]]:
    """Build the LiteLLM `messages` list: system + history + new user turn.

    `history` items are already `{"role", "content"}` dicts (loaded from
    the `chat_messages` table by the caller) and are passed through
    unchanged, in order, between the system message and the new user
    message.
    """
    system_message = {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{portfolio_context}"}
    return [system_message, *history, {"role": "user", "content": user_message}]


def is_mock_enabled() -> bool:
    """True when `LLM_MOCK` is set to "true" (case-insensitive)."""
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def generate_chat_response(
    portfolio_context: str, history: list[dict[str, str]], user_message: str
) -> ChatResponse:
    """Generate a structured chat response for the given conversation turn.

    Dispatches to the deterministic mock path when `LLM_MOCK=true`,
    otherwise calls `litellm.completion` via OpenRouter/Cerebras with
    Structured Outputs and parses the result into a `ChatResponse`.
    """
    if is_mock_enabled():
        return _mock_response(user_message, portfolio_context)

    # Imported lazily so importing this module (and running mock-mode
    # tests) never requires litellm to reach the network or find a key.
    from litellm import completion

    messages = build_messages(portfolio_context, history, user_message)
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    content = response.choices[0].message.content
    return ChatResponse.model_validate_json(content)


def _mock_response(user_message: str, portfolio_context: str) -> ChatResponse:
    """Deterministic, offline stand-in for the real LLM call.

    Parses directive tokens out of `user_message` (see module docstring)
    into typed `TradeIntent`/`WatchlistChange` actions and builds a plain
    English echo message summarizing what was parsed.
    """
    trades: list[TradeIntent] = []
    watchlist_changes: list[WatchlistChange] = []
    summary_parts: list[str] = []

    for side, ticker, quantity in _BUY_SELL_RE.findall(user_message):
        side_literal: Literal["buy", "sell"] = "buy" if side == "buy" else "sell"
        ticker_upper = ticker.upper()
        qty = float(quantity)
        trades.append(TradeIntent(ticker=ticker_upper, side=side_literal, quantity=qty))
        summary_parts.append(f"{side_literal} {qty} {ticker_upper}")

    for action, ticker in _WATCH_RE.findall(user_message):
        action_literal: Literal["add", "remove"] = "add" if action == "add" else "remove"
        ticker_upper = ticker.upper()
        watchlist_changes.append(WatchlistChange(ticker=ticker_upper, action=action_literal))
        summary_parts.append(f"{action_literal} {ticker_upper} to/from watchlist")

    if summary_parts:
        message = "[mock] Executed: " + "; ".join(summary_parts) + "."
    else:
        has_context = "yes" if portfolio_context.strip() else "no"
        message = (
            "[mock] Acknowledged your message. "
            f"(portfolio context provided: {has_context})"
        )

    return ChatResponse(message=message, trades=trades, watchlist_changes=watchlist_changes)
