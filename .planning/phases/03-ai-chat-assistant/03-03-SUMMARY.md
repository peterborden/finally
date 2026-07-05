---
phase: 03-ai-chat-assistant
plan: 03
subsystem: api
tags: [fastapi, sqlite, pydantic, chat, llm, portfolio, watchlist]

# Dependency graph
requires:
  - phase: 03-ai-chat-assistant (plan 03-02)
    provides: app/llm.py (generate_chat_response, ChatResponse/TradeIntent/WatchlistChange, is_mock_enabled, mock directive grammar)
  - phase: 02-trading-core
    provides: app/portfolio.py (build_portfolio, execute_trade over app.trade_engine.apply_trade)
  - phase: 02-trading-core
    provides: app/watchlist.py router + Phase 1 chat_messages schema
provides:
  - "POST /api/chat endpoint (app/chat.py, create_chat_router) — structured message + executed-action list"
  - "Reusable async add_ticker/remove_ticker(conn, market_source, ticker) service functions in app/watchlist.py"
  - "chat_messages persistence: user row (actions NULL) + assistant row (actions JSON) per turn"
affects: [04-frontend, 05-e2e-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auto-execution never aborts on one failed action: each trade/watchlist change is try/excepted individually and surfaced as an ActionResult(status='ok'|'error')"
    - "Chat orchestration reuses validated service functions (execute_trade, add_ticker, remove_ticker) rather than duplicating trade/watchlist math"

key-files:
  created:
    - backend/app/chat.py
    - backend/tests/test_chat.py
  modified:
    - backend/app/watchlist.py
    - backend/app/main.py

key-decisions:
  - "Renamed the watchlist router's inner route handlers to post_ticker/delete_ticker (from add_ticker/remove_ticker) to avoid shadowing the new module-level add_ticker/remove_ticker service functions in the same module"
  - "History is loaded BEFORE the new user message is persisted, so the just-sent message isn't duplicated into both history and the new user turn passed to generate_chat_response"
  - "ActionResult uses optional side/action/quantity/filled_price fields on one shared model (rather than two response types) so /api/chat has a single flat actions array mixing trades and watchlist changes"

requirements-completed: [CHAT-01, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07]

coverage:
  - id: D1
    description: "POST /api/chat returns a structured response (message + actions list) under LLM_MOCK=true"
    requirement: "CHAT-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_chat.py::TestChat::test_structured_response_returned"
        status: pass
    human_judgment: false
  - id: D2
    description: "Portfolio context (cash, positions w/ P&L, watchlist w/ live prices) is assembled from build_portfolio + live cache for the LLM prompt"
    requirement: "CHAT-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_chat.py::TestChat::test_mock_buy_directive_executes_trade"
        status: pass
    human_judgment: false
  - id: D3
    description: "LLM-specified trade auto-executes via app.portfolio.execute_trade and updates cash/positions"
    requirement: "CHAT-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_chat.py::TestChat::test_mock_buy_directive_executes_trade"
        status: pass
    human_judgment: false
  - id: D4
    description: "An invalid LLM trade (insufficient cash) is surfaced as an error ActionResult without aborting the response or mutating state"
    requirement: "CHAT-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_chat.py::TestChat::test_invalid_trade_surfaced_as_error_not_fatal"
        status: pass
    human_judgment: false
  - id: D5
    description: "LLM-specified watchlist change auto-applies via the extracted app.watchlist.add_ticker/remove_ticker service functions"
    requirement: "CHAT-05"
    verification:
      - kind: integration
        ref: "backend/tests/test_chat.py::TestChat::test_mock_watch_add_directive_updates_watchlist"
        status: pass
    human_judgment: false
  - id: D6
    description: "The user message and assistant message (actions as JSON) persist in chat_messages"
    requirement: "CHAT-06"
    verification:
      - kind: integration
        ref: "backend/tests/test_chat.py::TestChat::test_chat_messages_persisted_with_actions_json"
        status: pass
    human_judgment: false
  - id: D7
    description: "Existing watchlist router tests still pass after extracting add_ticker/remove_ticker as reusable service functions"
    verification:
      - kind: integration
        ref: "backend/tests/test_watchlist.py (6 tests)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-05
status: complete
---

# Phase 3 Plan 03: POST /api/chat endpoint Summary

**POST /api/chat orchestrating live portfolio context + generate_chat_response + auto-execution through the shared execute_trade/watchlist service paths, with per-action success/error surfacing and chat_messages persistence.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-05T02:57:00Z (approx, from prior wave completion)
- **Completed:** 2026-07-05T03:22:09Z
- **Tasks:** 3
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- `app/chat.py`: `create_chat_router()` exposing `POST /api/chat` — loads recent history + live portfolio/watchlist context, calls `app.llm.generate_chat_response`, auto-executes returned trades/watchlist changes, persists both chat turns, and returns `{message, actions}`.
- `app/watchlist.py` refactored: `add_ticker`/`remove_ticker` are now module-level async service functions taking an open connection + market source, reused by both the HTTP router and the new chat path — no duplicated DB/market-source logic.
- Chat router registered in `main.py` before the static mount.
- `tests/test_chat.py`: 5 integration tests under `LLM_MOCK=true`, covering the structured response shape, a mock-directive-driven trade, a mock-directive-driven watchlist add, an insufficient-cash trade surfaced as a non-fatal error, and chat_messages persistence with actions JSON.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract reusable watchlist add/remove service functions** - `56d62ec` (refactor)
2. **Task 2: Implement app/chat.py and register it in main.py** - `26efa54` (feat)
3. **Task 3: Integration tests for POST /api/chat under LLM_MOCK=true** - `37dd596` (test)

**Plan metadata:** (this commit, following)

## Files Created/Modified
- `backend/app/chat.py` - New POST /api/chat router: request/response models (ChatRequest, ActionResult, ChatResponseBody), portfolio-context builder, history loader, per-action auto-execution helpers (_apply_trades, _apply_watchlist_changes), chat_messages persistence
- `backend/app/watchlist.py` - Extracted `add_ticker`/`remove_ticker` module-level async service functions; router's POST/DELETE handlers renamed to `post_ticker`/`delete_ticker` and now delegate to the service functions
- `backend/app/main.py` - Imports and registers `create_chat_router()` before the static mount
- `backend/tests/test_chat.py` - New integration test suite for `/api/chat` under `LLM_MOCK=true`

## Decisions Made
- Renamed the watchlist router's inner `add_ticker`/`remove_ticker` route handlers to `post_ticker`/`delete_ticker` because Python's enclosing-scope name resolution would otherwise have the router handlers shadow the new module-level service functions of the same name within `create_watchlist_router()`, causing infinite self-recursion instead of delegating to the service layer. Route paths, methods, status codes, and response shapes are unchanged — `test_watchlist.py` passes verbatim.
- Loaded chat history from `chat_messages` BEFORE inserting the new user-turn row, so the just-sent message isn't duplicated into both the history list and the final user turn passed to `generate_chat_response`/`build_messages`.
- A single `ActionResult` model (with optional `side`/`action`/`quantity`/`filled_price` fields) represents both trade and watchlist outcomes, so `/api/chat` returns one flat `actions` array rather than two separately-typed lists — matches the plan's `{message, actions}` response shape.

## Deviations from Plan

None - plan executed exactly as written. The `post_ticker`/`delete_ticker` handler rename inside `create_watchlist_router()` is an internal-naming adjustment required to make the plan's explicit `add_ticker`/`remove_ticker` module-level function names work without breaking the existing router (Rule 3 — blocking issue: without the rename, the router's own decorated functions would shadow and recursively call themselves instead of the new service functions). No behavior, route, or test changed.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. All tests run under `LLM_MOCK=true` with zero network access to OpenRouter.

## Next Phase Readiness
- `POST /api/chat` is fully wired: live portfolio context, auto-execution through the same validated trade/watchlist paths as manual actions, and persisted conversation history — ready for the Phase 4 frontend chat panel to consume directly.
- Full backend suite (150 tests) passes: `uv run --extra dev pytest -q`.
- `uv run ruff check app/chat.py app/watchlist.py app/main.py` clean.
- No blockers for Phase 4 (frontend) or Phase 5 (E2E tests), which can drive `/api/chat` under `LLM_MOCK=true` exactly as `test_chat.py` does.

---
*Phase: 03-ai-chat-assistant*
*Completed: 2026-07-05*

## Self-Check: PASSED

All created/modified files and task commit hashes verified present on disk and in git history.
