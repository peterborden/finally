"""Prompt construction for the chat assistant (PLAN §9).

Assembles the message list sent to the LLM: a system prompt, a compact
snapshot of the user's portfolio + watchlist, recent conversation history,
and the user's new message.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """\
You are FinAlly, an AI trading assistant embedded in a simulated trading workstation.
The user trades a virtual portfolio starting from $10,000 in fake cash — there is no real money at stake.

Your responsibilities:
- Analyze the user's portfolio composition, risk concentration, and profit/loss.
- Suggest trades with clear, data-driven reasoning.
- Execute trades when the user asks for them or agrees to a suggestion. Market orders only, instant fill at the live price.
- Manage the watchlist proactively (add tickers you discuss, remove ones no longer relevant).
- Be concise and data-driven. Reference concrete numbers from the portfolio context.

Response format — you MUST return a single JSON object matching this schema:
{
  "message": "your conversational reply to the user",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}
Rules:
- "message" is required and is the only text shown to the user. Put ALL explanation there.
- "trades" and "watchlist_changes" are optional; use [] when there is nothing to do.
- "side" is "buy" or "sell". "action" is "add" or "remove". "quantity" is a positive number (fractional shares allowed).
- Only include a trade when you actually intend to execute it now. Each trade is validated
  (sufficient cash to buy, sufficient shares to sell); if it fails you will be told so you can inform the user.
- Never wrap the JSON in markdown fences or add commentary outside the JSON object.
"""


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_price(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def build_watchlist_context(watchlist_rows: list[dict], price_cache: Any) -> list[dict]:
    """Combine watchlist rows (from the DB) with live prices from the cache into
    a compact list of dicts for prompt rendering.

    Each item: {ticker, price, change_percent, direction}. Price fields are None
    until the first tick for that ticker arrives.
    """
    context: list[dict] = []
    for row in watchlist_rows or []:
        ticker = row.get("ticker") if isinstance(row, dict) else None
        if not ticker:
            continue
        update = price_cache.get(ticker) if price_cache is not None else None
        if update is not None:
            context.append(
                {
                    "ticker": ticker,
                    "price": update.price,
                    "change_percent": round(update.change_percent, 2),
                    "direction": update.direction,
                }
            )
        else:
            context.append(
                {"ticker": ticker, "price": None, "change_percent": None, "direction": "flat"}
            )
    return context


def _render_portfolio(portfolio_state: dict | None) -> str:
    if not portfolio_state:
        return "Portfolio: unavailable."

    lines = [
        "PORTFOLIO",
        f"- Cash balance: {_fmt_money(portfolio_state.get('cash_balance'))}",
        f"- Positions value: {_fmt_money(portfolio_state.get('positions_value'))}",
        f"- Total value: {_fmt_money(portfolio_state.get('total_value'))}",
        f"- Total unrealized P&L: {_fmt_money(portfolio_state.get('total_unrealized_pnl'))}",
    ]
    positions = portfolio_state.get("positions") or []
    if positions:
        lines.append("- Positions:")
        for p in positions:
            pct = p.get("unrealized_pnl_percent")
            pct_str = f"{pct:+.2f}%" if isinstance(pct, (int, float)) else "n/a"
            lines.append(
                f"    {p.get('ticker')}: qty {p.get('quantity')}, "
                f"avg cost {_fmt_price(p.get('avg_cost'))}, "
                f"price {_fmt_price(p.get('current_price'))}, "
                f"unrealized P&L {_fmt_money(p.get('unrealized_pnl'))} ({pct_str})"
            )
    else:
        lines.append("- Positions: none (all cash).")
    return "\n".join(lines)


def _render_watchlist(watchlist_context: list[dict] | None) -> str:
    if not watchlist_context:
        return "WATCHLIST: empty."
    lines = ["WATCHLIST (live prices):"]
    for item in watchlist_context:
        price = item.get("price")
        if price is None:
            lines.append(f"- {item.get('ticker')}: price pending")
        else:
            pct = item.get("change_percent")
            pct_str = f"{pct:+.2f}%" if isinstance(pct, (int, float)) else "n/a"
            lines.append(f"- {item.get('ticker')}: {_fmt_price(price)} ({pct_str} today)")
    return "\n".join(lines)


def build_context_block(portfolio_state: dict | None, watchlist_context: list[dict] | None) -> str:
    """Render the portfolio + watchlist snapshot injected as a system message."""
    return (
        "Current account snapshot (use these numbers in your analysis):\n\n"
        + _render_portfolio(portfolio_state)
        + "\n\n"
        + _render_watchlist(watchlist_context)
    )


def build_messages(
    user_message: str,
    portfolio_state: dict | None,
    watchlist_context: list[dict] | None,
    history: list[dict] | None,
) -> list[dict]:
    """Assemble the full message list for the LLM call.

    Order: system prompt, account-snapshot system message, prior conversation
    turns (oldest→newest), then the user's new message.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_context_block(portfolio_state, watchlist_context)},
    ]

    for msg in history or []:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages
