"""AI chat REST API: POST /api/chat.

Orchestrates the LLM chat turn: loads live portfolio context and recent
`chat_messages` history, calls `app.llm.generate_chat_response` for a
structured reply, auto-executes any returned trades/watchlist changes
through the SAME validated service paths as the manual endpoints
(`app.portfolio.execute_trade`, `app.watchlist.add_ticker`/`remove_ticker`),
and persists both the user and assistant turns.

No trade math or watchlist logic is duplicated here -- this module is pure
orchestration + persistence, per planning/PLAN.md section 9.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from .db import get_connection, get_db_path
from .llm import ChatResponse, generate_chat_response
from .portfolio import build_portfolio, execute_trade
from .trade_engine import Side, TradeError
from .watchlist import add_ticker, remove_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_USER_ID = "default"

# Number of most-recent chat_messages rows loaded as conversation history
# for the LLM prompt -- bounded so the prompt (and the query) never grow
# unbounded with the full conversation log (T-03-06).
_HISTORY_LIMIT = 20


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str


class ActionResult(BaseModel):
    """The outcome of one auto-executed trade or watchlist change.

    Exposed in the response so the LLM's (and validation's) successes and
    failures are visible to the user -- a failed trade never aborts the
    rest of the chat turn (CHAT-04).
    """

    type: Literal["trade", "watchlist"]
    ticker: str
    status: Literal["ok", "error"]
    detail: str
    side: Literal["buy", "sell"] | None = None
    action: Literal["add", "remove"] | None = None
    quantity: float | None = None
    filled_price: float | None = None


class ChatResponseBody(BaseModel):
    """Response body for POST /api/chat."""

    message: str
    actions: list[ActionResult]


def _load_history(conn, user_id: str, limit: int) -> list[dict[str, str]]:
    """Load the most recent `limit` chat_messages rows, oldest first.

    Ordered DESC in SQL (to bound by recency) then reversed in Python so
    the returned list is chronological, as `app.llm.build_messages` expects.
    """
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def _build_portfolio_context(conn, cache) -> str:
    """Render a concise, human-readable portfolio + watchlist context string.

    Includes cash, each position with its live valuation and unrealized
    P&L, total portfolio value/P&L, and the watchlist with live prices
    (CHAT-03).
    """
    portfolio = build_portfolio(conn, cache)

    lines = [
        f"Cash balance: ${portfolio.cash_balance:.2f}",
        f"Total portfolio value: ${portfolio.total_value:.2f}",
        f"Total unrealized P&L: ${portfolio.total_unrealized_pnl:.2f}",
    ]

    if portfolio.positions:
        lines.append("Positions:")
        for position in portfolio.positions:
            lines.append(
                f"  {position.ticker}: {position.quantity} shares @ avg cost "
                f"${position.avg_cost:.2f}, current price ${position.current_price:.2f}, "
                f"unrealized P&L ${position.unrealized_pnl:.2f} "
                f"({position.pct_change * 100:.2f}%)"
            )
    else:
        lines.append("Positions: none")

    watchlist_rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (_USER_ID,),
    ).fetchall()
    if watchlist_rows:
        lines.append("Watchlist:")
        for row in watchlist_rows:
            ticker = row["ticker"]
            price = cache.get_price(ticker)
            price_text = f"${price:.2f}" if price is not None else "no live price"
            lines.append(f"  {ticker}: {price_text}")
    else:
        lines.append("Watchlist: empty")

    return "\n".join(lines)


def _insert_chat_message(
    conn, role: str, content: str, actions: list[ActionResult] | None
) -> None:
    """Insert one chat_messages row. Does not commit -- caller commits."""
    actions_json = (
        json.dumps([action.model_dump() for action in actions]) if actions is not None else None
    )
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            uuid.uuid4().hex,
            _USER_ID,
            role,
            content,
            actions_json,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


async def _apply_trades(conn, cache, response: ChatResponse) -> list[ActionResult]:
    """Auto-execute each LLM-specified trade via the shared execute_trade path.

    A TradeError (insufficient cash/shares, invalid input) is captured as an
    error ActionResult rather than propagated -- one bad trade never aborts
    the rest of the chat turn or the response (CHAT-04, T-03-05).
    """
    results: list[ActionResult] = []
    for trade in response.trades:
        try:
            result = execute_trade(conn, cache, trade.ticker, Side(trade.side), trade.quantity)
        except TradeError as exc:
            results.append(
                ActionResult(
                    type="trade",
                    ticker=trade.ticker,
                    status="error",
                    detail=str(exc),
                    side=trade.side,
                    quantity=trade.quantity,
                )
            )
            continue

        results.append(
            ActionResult(
                type="trade",
                ticker=trade.ticker,
                status="ok",
                detail=f"Filled {result.filled_quantity} {trade.ticker} @ {result.filled_price}",
                side=trade.side,
                quantity=result.filled_quantity,
                filled_price=result.filled_price,
            )
        )
    return results


async def _apply_watchlist_changes(
    conn, market_source, response: ChatResponse
) -> list[ActionResult]:
    """Auto-apply each LLM-specified watchlist change via the shared service functions.

    Any exception is captured as an error ActionResult rather than
    propagated, matching the trade path's never-abort behavior.
    """
    results: list[ActionResult] = []
    for change in response.watchlist_changes:
        try:
            if change.action == "add":
                await add_ticker(conn, market_source, change.ticker)
                detail = f"Added {change.ticker} to watchlist"
            else:
                await remove_ticker(conn, market_source, change.ticker)
                detail = f"Removed {change.ticker} from watchlist"
        except Exception as exc:  # noqa: BLE001 - surfaced as an ActionResult, not raised
            results.append(
                ActionResult(
                    type="watchlist",
                    ticker=change.ticker,
                    status="error",
                    detail=str(exc),
                    action=change.action,
                )
            )
            continue

        results.append(
            ActionResult(
                type="watchlist",
                ticker=change.ticker,
                status="ok",
                detail=detail,
                action=change.action,
            )
        )
    return results


def create_chat_router() -> APIRouter:
    """Create the chat router (factory pattern, no module-level globals).

    Cache, market source, and the DB connection are all obtained per-request
    from `request.app.state` / `get_connection`, mirroring the portfolio and
    watchlist routers.
    """

    @router.post("")
    async def post_chat(body: ChatRequest, request: Request) -> ChatResponseBody:
        """POST /api/chat (CHAT-01, CHAT-03, CHAT-04, CHAT-05, CHAT-06)."""
        cache = request.app.state.price_cache
        market_source = request.app.state.market_source

        conn = get_connection(get_db_path())
        try:
            history = _load_history(conn, _USER_ID, _HISTORY_LIMIT)
            context_text = _build_portfolio_context(conn, cache)

            _insert_chat_message(conn, role="user", content=body.message, actions=None)
            conn.commit()

            response: ChatResponse = generate_chat_response(context_text, history, body.message)

            actions: list[ActionResult] = []
            actions.extend(await _apply_trades(conn, cache, response))
            actions.extend(await _apply_watchlist_changes(conn, market_source, response))

            _insert_chat_message(
                conn, role="assistant", content=response.message, actions=actions
            )
            conn.commit()
        finally:
            conn.close()

        return ChatResponseBody(message=response.message, actions=actions)

    return router


__all__ = [
    "ChatRequest",
    "ActionResult",
    "ChatResponseBody",
    "create_chat_router",
]
