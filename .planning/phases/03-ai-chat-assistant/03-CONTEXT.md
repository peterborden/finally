# Phase 3: AI Chat Assistant - Context

**Gathered:** 2026-07-04
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

An LLM chat endpoint `POST /api/chat` that loads live portfolio context, calls the LLM via LiteLLM → OpenRouter (Cerebras) with structured output, auto-executes any trades/watchlist changes it returns, persists the conversation, and supports a deterministic `LLM_MOCK=true` mode. Requirements: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07.

</domain>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.claude/skills/cerebras/SKILL.md` — REQUIRED: how to call the LLM using LiteLLM + OpenRouter with the Cerebras inference provider. Use this skill's exact pattern for the LLM call.
- `planning/PLAN.md` §9 (LLM Integration) — authoritative: how chat works, the structured output schema, auto-execution rules, system-prompt guidance, LLM_MOCK behavior.
- `backend/app/portfolio.py` — `execute_trade(...)` is the single validated trade path the AI MUST reuse for LLM-initiated trades; `build_portfolio(...)` builds the portfolio context.
- `backend/app/watchlist.py` — the watchlist add/remove logic the AI reuses for watchlist_changes.
- `backend/app/db/` — connection + `chat_messages` table (already in schema from Phase 1).

</canonical_refs>

<decisions>
## Implementation Decisions

### Claude's Discretion (guided by PLAN.md §9)
- **LLM call:** Use the `cerebras-inference` skill exactly — LiteLLM → OpenRouter, model `openrouter/openai/gpt-oss-120b`, Cerebras provider, structured outputs. `OPENROUTER_API_KEY` from the project-root `.env` (already gitignored). Read the SKILL.md before writing the call.
- **Structured output schema** (PLAN.md §9): `{ "message": str (required), "trades": [{ticker, side, quantity}]?, "watchlist_changes": [{ticker, action: add|remove}]? }`. Use a Pydantic model for the response schema and pass it to the structured-output call.
- **Flow per request (POST /api/chat {message}):** (1) load portfolio context (cash, positions with P&L, watchlist with live prices from PriceCache, total value) + recent chat_messages history; (2) build system prompt ("FinAlly, an AI trading assistant" per §9 guidance) + context + history + new user message; (3) call LLM (or mock) for structured JSON; (4) auto-execute trades via `app.portfolio.execute_trade` and watchlist_changes via the watchlist logic — SAME validation as manual; collect per-action results/errors; (5) persist the user message and the assistant message (with executed actions as JSON in `chat_messages.actions`); (6) return the full structured response incl. the message, executed actions, and any errors so the LLM's failures are surfaced to the user.
- **Auto-execution:** No confirmation. If a trade fails validation (insufficient cash/shares), capture the error and include it in the response (so the assistant/user sees it); do not abort the whole response. Watchlist add/remove likewise.
- **LLM_MOCK=true:** Return a deterministic response without calling OpenRouter — enables E2E/CI and dev without a key. The mock should still exercise the full auto-execution path (e.g., a mock that echoes context and optionally performs a trivial deterministic action) so tests can assert action execution. Keep the mock behavior documented and stable.
- **Persistence:** append a `chat_messages` row for the user message (role=user, actions=null) and one for the assistant (role=assistant, content=message, actions=JSON of executed trades/watchlist changes). Load recent history (e.g., last N) for context.
- **Module layout:** `app/chat.py` (router factory `create_chat_router()` + service) reusing app.state.price_cache/market_source and the db connection; keep the LLM client wrapper separable (e.g., `app/llm.py`) so mock vs real is a clean switch on `LLM_MOCK`.

</decisions>

<code_context>
## Existing Code Insights

Phases 1-2 built: FastAPI app (create_app, lifespan with price_cache + market_source + snapshot task on app.state), db layer (chat_messages table already created), portfolio.py (execute_trade, build_portfolio, compute_and_record_snapshot), watchlist.py (add/remove wired to market source), trade_engine.py (pure apply_trade). Reuse these — do not duplicate trade/watchlist logic.

</code_context>

<specifics>
## Specific Ideas

System prompt should instruct the model to: analyze portfolio composition/risk/P&L, suggest trades with reasoning, execute trades when asked/agreed, manage the watchlist, be concise and data-driven, and ALWAYS return valid structured JSON matching the schema (PLAN.md §9 System Prompt Guidance). litellm is likely a new dependency — add it to pyproject.toml (the cerebras skill will specify). python-dotenv is already a dependency for reading .env.

</specifics>

<deferred>
## Deferred Ideas

Token-by-token streaming is Out of Scope (Cerebras is fast; a loading indicator suffices — the frontend handles that in Phase 4).

</deferred>
