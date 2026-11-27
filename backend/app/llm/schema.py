"""Structured-output schema for the LLM chat assistant (PLAN §6 / §9).

The model is asked to return JSON of the shape::

    {
      "message": "conversational reply",
      "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
      "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
    }

``parse_llm_response`` is deliberately tolerant: structured outputs *should* conform,
but the model can still emit malformed or partially-invalid JSON, so we degrade
gracefully instead of raising into the request handler.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Side = Literal["buy", "sell"]
WatchlistAction = Literal["add", "remove"]

# Fallback text used when the model output cannot be parsed at all.
_UNPARSEABLE_FALLBACK = (
    "Sorry, I couldn't produce a valid response just now. Please try rephrasing your request."
)


class TradeInstruction(BaseModel):
    """A single trade the assistant wants to auto-execute."""

    ticker: str
    side: Side
    quantity: float = Field(gt=0)

    @field_validator("ticker", mode="before")
    @classmethod
    def _norm_ticker(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("side", mode="before")
    @classmethod
    def _norm_side(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class WatchlistChange(BaseModel):
    """A single watchlist add/remove the assistant wants to apply."""

    ticker: str
    action: WatchlistAction

    @field_validator("ticker", mode="before")
    @classmethod
    def _norm_ticker(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("action", mode="before")
    @classmethod
    def _norm_action(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class LLMResponse(BaseModel):
    """Top-level structured response returned by the assistant."""

    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


def _coerce_item(model: type[BaseModel], raw: Any) -> BaseModel | None:
    """Validate one list item, returning None if it is individually invalid."""
    if not isinstance(raw, dict):
        return None
    try:
        return model.model_validate(raw)
    except Exception:
        return None


def _lenient_parse(data: dict[str, Any]) -> LLMResponse:
    """Build an LLMResponse from a dict, dropping individually-invalid list items
    rather than failing the whole response."""
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        message = _UNPARSEABLE_FALLBACK

    trades: list[TradeInstruction] = []
    for raw in data.get("trades") or []:
        item = _coerce_item(TradeInstruction, raw)
        if item is not None:
            trades.append(item)  # type: ignore[arg-type]

    changes: list[WatchlistChange] = []
    for raw in data.get("watchlist_changes") or []:
        item = _coerce_item(WatchlistChange, raw)
        if item is not None:
            changes.append(item)  # type: ignore[arg-type]

    return LLMResponse(message=message, trades=trades, watchlist_changes=changes)


def parse_llm_response(raw: str | None) -> LLMResponse:
    """Parse raw model output into an ``LLMResponse``, degrading gracefully.

    Tiers:
      1. Strict validation of the full JSON object.
      2. Lenient parse: keep ``message``, drop only the invalid list items.
      3. Total fallback: a safe message with no actions (never raises).
    """
    if not raw or not raw.strip():
        return LLMResponse(message=_UNPARSEABLE_FALLBACK)

    text = raw.strip()

    # Strict path — the happy case for structured outputs.
    try:
        return LLMResponse.model_validate_json(text)
    except Exception:
        pass

    # Lenient path — recover a usable object from parseable-but-nonconforming JSON.
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return _lenient_parse(data)
    except Exception:
        pass

    # Total fallback — treat whatever we got as plain conversational text.
    return LLMResponse(message=text if len(text) <= 2000 else _UNPARSEABLE_FALLBACK)
