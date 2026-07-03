"""POST /api/chat — the AI trading assistant endpoint (PLAN §9, contract §5.7).

Flow:
  1. Load context: recent chat history + watchlist (DB) and portfolio state (service).
  2. Call the LLM (mock or real Cerebras) for a structured response.
  3. Auto-execute each trade via ``services.portfolio.execute_trade`` and each
     watchlist change via ``services.watchlist`` — collecting failures into ``errors``.
  4. ``trades`` / ``watchlist_changes`` in the response reflect only what ACTUALLY executed.
  5. Persist the user + assistant messages to ``chat_messages`` (assistant row carries
     the executed ``actions`` as JSON).

Cross-module deps (``app.services.portfolio``, ``app.services.watchlist``, ``app.db``,
``app.llm.client.generate_response``) are resolved through FastAPI dependency providers
that import lazily. This keeps the LLM worktree buildable/green in isolation and lets
unit tests override every dependency. ``main.py`` (Backend) must ``include_router`` this
router and expose the price cache + market source on ``app.state``.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from app.llm.prompt import build_watchlist_context

logger = logging.getLogger(__name__)

router = APIRouter()

HISTORY_LIMIT = 20

# app.state attribute names this router reads (primary first, then aliases).
_PRICE_CACHE_ATTRS = ("price_cache", "cache")
_MARKET_SOURCE_ATTRS = ("market_source", "source", "data_source", "market")


# --------------------------------------------------------------------------- #
# Request / response models (contract §5.7)
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class ChatResponse(BaseModel):
    message: str
    trades: list[dict] = Field(default_factory=list)
    watchlist_changes: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Dependency providers (lazy imports; overridable in tests)
# --------------------------------------------------------------------------- #
def get_generate_fn() -> Callable[..., Any]:
    from app.llm.client import generate_response

    return generate_response


def get_portfolio_service() -> Any:
    from app.services import portfolio

    return portfolio


def get_watchlist_service() -> Any:
    from app.services import watchlist

    return watchlist


def get_db() -> Any:
    from app import db

    return db


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _state_any(request: Request, names: tuple[str, ...]) -> Any:
    state = request.app.state
    for name in names:
        value = getattr(state, name, None)
        if value is not None:
            return value
    return None


def _fmt_qty(quantity: float) -> str:
    return str(int(quantity)) if float(quantity) == int(quantity) else str(quantity)


def _trade_dict(trade: Any) -> dict:
    """Project a recorded trade row to the §5.7 trade shape."""
    if not isinstance(trade, dict):
        return {"trade": trade}
    return {k: trade.get(k) for k in ("ticker", "side", "quantity", "price", "executed_at")}


async def _apply_watchlist_change(
    watchlist_service: Any, change: Any, source: Any, price_cache: Any
) -> tuple[bool, str | None]:
    """Apply one watchlist add/remove. Returns (executed, error_message)."""
    try:
        if change.action == "add":
            result = watchlist_service.add_ticker(change.ticker, source, price_cache)
        else:
            result = watchlist_service.remove_ticker(change.ticker, source)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Watchlist %s failed for %s", change.action, change.ticker)
        return False, f"Could not {change.action} {change.ticker}: {exc}"

    if change.action == "remove" and result is False:
        return False, f"{change.ticker} was not in your watchlist."
    return True, None


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    generate_fn: Callable[..., Any] = Depends(get_generate_fn),
    portfolio_service: Any = Depends(get_portfolio_service),
    watchlist_service: Any = Depends(get_watchlist_service),
    db: Any = Depends(get_db),
) -> ChatResponse:
    price_cache = _state_any(request, _PRICE_CACHE_ATTRS)
    source = _state_any(request, _MARKET_SOURCE_ATTRS)
    user_message = payload.message

    # 1. Load context (best-effort — a context read failure must not 500 the chat).
    history: list[dict] = []
    watchlist_rows: list[dict] = []
    try:
        with db.connection() as conn:
            history = db.get_recent_messages(conn, limit=HISTORY_LIMIT)
            watchlist_rows = db.get_watchlist(conn)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load chat context from DB")

    try:
        portfolio_state = portfolio_service.get_portfolio_state(price_cache)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load portfolio state")
        portfolio_state = None

    watchlist_context = build_watchlist_context(watchlist_rows, price_cache)

    # 2. Call the LLM (blocking call runs off the event loop).
    llm_response = await run_in_threadpool(
        generate_fn, user_message, portfolio_state, watchlist_context, history
    )

    # 3. Auto-execute actions; record only what actually succeeded.
    executed_trades: list[dict] = []
    executed_changes: list[dict] = []
    errors: list[str] = []

    for trade in llm_response.trades:
        try:
            result = portfolio_service.execute_trade(
                trade.ticker, trade.side, trade.quantity, price_cache
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("execute_trade raised for %s", trade.ticker)
            errors.append(f"Could not {trade.side} {_fmt_qty(trade.quantity)} {trade.ticker}: {exc}")
            continue

        if getattr(result, "success", False):
            executed_trades.append(_trade_dict(getattr(result, "trade", None)))
        else:
            reason = getattr(result, "error", None) or "trade rejected"
            errors.append(
                f"Could not {trade.side} {_fmt_qty(trade.quantity)} {trade.ticker}: {reason}"
            )

    for change in llm_response.watchlist_changes:
        executed, error = await _apply_watchlist_change(
            watchlist_service, change, source, price_cache
        )
        if executed:
            executed_changes.append({"ticker": change.ticker, "action": change.action})
        elif error:
            errors.append(error)

    # 4. Persist user + assistant messages (assistant carries executed actions).
    actions = {
        "trades": executed_trades,
        "watchlist_changes": executed_changes,
        "errors": errors,
    }
    try:
        with db.connection() as conn:
            db.add_message(conn, "user", user_message)
            db.add_message(conn, "assistant", llm_response.message, actions=actions)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist chat messages")

    # 5. Respond (contract §5.7).
    return ChatResponse(
        message=llm_response.message,
        trades=executed_trades,
        watchlist_changes=executed_changes,
        errors=errors,
    )
