"""Deterministic mock LLM (PLAN §9 "LLM Mock Mode").

When ``LLM_MOCK=true`` the chat endpoint uses this instead of calling OpenRouter.
It parses a few simple natural-language intents so that E2E tests can assert a
real trade / watchlist change actually happens:

  - "buy 5 AAPL" / "buy 5 shares of AAPL" / "buy 5 shares of Apple"
  - "sell 2 TSLA" / "sell 2 shares of Tesla"
  - "add PYPL to watchlist" / "watch PYPL"
  - "remove NFLX" / "remove NFLX from watchlist" / "unwatch NFLX"

Everything is deterministic (no randomness, no clock) so responses are reproducible.
"""

from __future__ import annotations

import re

from .schema import LLMResponse, TradeInstruction, WatchlistChange

# A small company-name → ticker map so plain-English demo phrases ("buy 5 shares
# of Apple") still resolve to a tradeable ticker in mock mode.
_NAME_TO_TICKER = {
    "APPLE": "AAPL",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "MICROSOFT": "MSFT",
    "AMAZON": "AMZN",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
    "META": "META",
    "FACEBOOK": "META",
    "NETFLIX": "NFLX",
    "VISA": "V",
    "JPMORGAN": "JPM",
    "PAYPAL": "PYPL",
}

_TRADE_RE = re.compile(
    r"\b(?P<side>buy|sell)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?(?P<sym>[A-Za-z]{1,12})\b",
    re.IGNORECASE,
)

# add/watch a ticker
_WATCH_ADD_RE = re.compile(
    r"\b(?:add|watch)\s+(?P<sym>[A-Za-z]{1,12})\b",
    re.IGNORECASE,
)

# remove/unwatch a ticker
_WATCH_REMOVE_RE = re.compile(
    r"\b(?:remove|unwatch|delete|drop)\s+(?P<sym>[A-Za-z]{1,12})\b",
    re.IGNORECASE,
)

# Words that follow the verb but are not tickers (avoid false positives).
_STOPWORDS = {"SHARES", "SHARE", "TO", "FROM", "THE", "MY", "OF", "A", "AN", "AND"}


def _resolve_symbol(raw: str) -> str:
    sym = raw.strip().upper()
    return _NAME_TO_TICKER.get(sym, sym)


def _parse_trades(text: str) -> list[TradeInstruction]:
    trades: list[TradeInstruction] = []
    for m in _TRADE_RE.finditer(text):
        sym = _resolve_symbol(m.group("sym"))
        if sym in _STOPWORDS:
            continue
        try:
            qty = float(m.group("qty"))
        except ValueError:
            continue
        if qty <= 0:
            continue
        trades.append(TradeInstruction(ticker=sym, side=m.group("side").lower(), quantity=qty))
    return trades


def _parse_watchlist(text: str) -> list[WatchlistChange]:
    changes: list[WatchlistChange] = []
    seen: set[tuple[str, str]] = set()

    for m in _WATCH_REMOVE_RE.finditer(text):
        sym = _resolve_symbol(m.group("sym"))
        if sym in _STOPWORDS:
            continue
        key = (sym, "remove")
        if key not in seen:
            seen.add(key)
            changes.append(WatchlistChange(ticker=sym, action="remove"))

    for m in _WATCH_ADD_RE.finditer(text):
        sym = _resolve_symbol(m.group("sym"))
        if sym in _STOPWORDS:
            continue
        # Don't double-count a symbol already handled as a removal.
        if (sym, "remove") in seen:
            continue
        key = (sym, "add")
        if key not in seen:
            seen.add(key)
            changes.append(WatchlistChange(ticker=sym, action="add"))

    return changes


def _compose_message(
    trades: list[TradeInstruction], changes: list[WatchlistChange]
) -> str:
    parts: list[str] = []
    for t in trades:
        verb = "Buying" if t.side == "buy" else "Selling"
        qty = int(t.quantity) if t.quantity == int(t.quantity) else t.quantity
        parts.append(f"{verb} {qty} share{'s' if qty != 1 else ''} of {t.ticker}.")
    for c in changes:
        if c.action == "add":
            parts.append(f"Added {c.ticker} to your watchlist.")
        else:
            parts.append(f"Removed {c.ticker} from your watchlist.")
    if parts:
        return " ".join(parts)
    return (
        "[mock] I'm FinAlly running in offline test mode. Ask me to buy or sell a "
        "ticker (e.g. 'buy 5 AAPL') or to add/remove a watchlist symbol and I'll execute it."
    )


def mock_response(user_message: str) -> LLMResponse:
    """Deterministically turn a user message into an ``LLMResponse``."""
    text = user_message or ""
    trades = _parse_trades(text)
    changes = _parse_watchlist(text)
    return LLMResponse(
        message=_compose_message(trades, changes),
        trades=trades,
        watchlist_changes=changes,
    )
