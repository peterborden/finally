---
phase: 03-ai-chat-assistant
plan: 02
subsystem: ai-integration
tags: [litellm, openrouter, cerebras, pydantic, structured-outputs, llm]

# Dependency graph
requires:
  - phase: 03-ai-chat-assistant
    provides: litellm and pydantic runtime deps resolved in backend uv env (03-01)
provides:
  - app/llm.py exposing ChatResponse/TradeIntent/WatchlistChange, build_messages, is_mock_enabled, generate_chat_response
  - deterministic LLM_MOCK directive grammar ([[buy:T:Q]], [[sell:T:Q]], [[watch-add:T]], [[watch-remove:T]]) for offline testing/E2E
affects: [03-03 (chat HTTP endpoint + auto-execution), Phase 5 (Playwright E2E chat scenarios)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Lazy `from litellm import completion` import inside the real call branch so importing app.llm and running mock-mode code never requires a network stack or API key"]

key-files:
  created: [backend/app/llm.py, backend/tests/test_llm.py]
  modified: []

key-decisions:
  - "generate_chat_response() is the single entry point; app.llm never imports fastapi/sqlite3/app.portfolio so it stays unit-testable in isolation and transport-agnostic for plan 03-03"
  - "Mock directive tokens ([[buy:T:Q]] etc.) are a documented, stable contract (module docstring) so downstream tests and the Phase 5 Playwright suite can drive real trade/watchlist actions without an OpenRouter key"
  - "litellm.completion is imported lazily inside generate_chat_response's real branch, not at module top level, keeping mock-mode import/execution fully network-free"

patterns-established:
  - "Structured-output LLM calls: response_format=<PydanticModel>, then Model.model_validate_json(response.choices[0].message.content)"

requirements-completed: [CHAT-02, CHAT-03, CHAT-07]

coverage:
  - id: D1
    description: "ChatResponse/TradeIntent/WatchlistChange Pydantic schema parses message-only and nested trades/watchlist_changes payloads"
    requirement: "CHAT-02"
    verification:
      - kind: unit
        ref: "tests/test_llm.py#TestChatResponseSchema"
        status: pass
    human_judgment: false
  - id: D2
    description: "is_mock_enabled() reads LLM_MOCK case-insensitively (true/TRUE/True vs false/unset)"
    requirement: "CHAT-07"
    verification:
      - kind: unit
        ref: "tests/test_llm.py#TestIsMockEnabled"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mock path parses [[buy:T:Q]]/[[sell:T:Q]]/[[watch-add:T]]/[[watch-remove:T]] directives into typed actions with zero network calls"
    requirement: "CHAT-07"
    verification:
      - kind: unit
        ref: "tests/test_llm.py#TestMockPath"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real path calls litellm.completion with MODEL/response_format=ChatResponse/EXTRA_BODY/reasoning_effort and parses the structured JSON result"
    requirement: "CHAT-02"
    verification:
      - kind: unit
        ref: "tests/test_llm.py#TestRealPath::test_calls_completion_with_expected_args_and_parses_result"
        status: pass
    human_judgment: false
  - id: D5
    description: "build_messages() orders system (with portfolio context) first, then history, then the new user message"
    requirement: "CHAT-03"
    verification:
      - kind: unit
        ref: "tests/test_llm.py#TestBuildMessages"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-07-04
status: complete
---

# Phase 3 Plan 2: LLM Chat Wrapper Summary

**app/llm.py wrapping LiteLLM/OpenRouter/Cerebras structured-output calls behind generate_chat_response(), with a deterministic offline LLM_MOCK directive grammar for trades and watchlist changes**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 (both auto; Task 1 tdd="true")
- **Files modified:** 2 (both created)

## Accomplishments
- `ChatResponse`/`TradeIntent`/`WatchlistChange` Pydantic v2 schema (Python 3.10+ union/Literal syntax) matching PLAN.md §9's structured-output contract, with `trades`/`watchlist_changes` defaulting to empty lists
- `build_messages()` assembles `[system(+portfolio context), *history, user]` in the required order
- `generate_chat_response()` — single public entry point — dispatches to either the real Cerebras call (`litellm.completion` via OpenRouter, `response_format=ChatResponse`, `reasoning_effort="low"`, `extra_body={"provider":{"order":["cerebras"]}}`, exactly per `.claude/skills/cerebras/SKILL.md`) or the deterministic mock path
- `_mock_response()` implements a documented, stable directive grammar (`[[buy:TICKER:QTY]]`, `[[sell:TICKER:QTY]]`, `[[watch-add:TICKER]]`, `[[watch-remove:TICKER]]`) so `LLM_MOCK=true` tests and the future Phase 5 Playwright suite can drive real trade/watchlist actions offline
- 14 new unit tests in `tests/test_llm.py` covering schema parsing, `is_mock_enabled()` truthiness, all four mock directives + the no-directive path (with `litellm.completion` patched to raise if ever called, proving zero network I/O), the real path (patched stub asserting exact call kwargs: `model`, `response_format`, `extra_body`, `reasoning_effort`), and `build_messages()` ordering
- Ruff-clean; full backend suite (145 tests) passes after this plan

## Task Commits

1. **Task 1: Implement app/llm.py — schema, prompt builder, Cerebras call, mock (CHAT-02, CHAT-03, CHAT-07)** - `ba60df2` (feat)
2. **Task 2: Unit tests for app/llm.py — mock path + patched real path (CHAT-02, CHAT-07)** - `cb0b280` (test)

**Plan metadata:** committed with final phase-level docs commit (see combined report)

## Files Created/Modified
- `backend/app/llm.py` - LLM wrapper: schema, prompt builder, real Cerebras call, deterministic mock
- `backend/tests/test_llm.py` - 14 unit tests, no network I/O in any test

## Decisions Made
- Kept `app/llm.py` transport-only per the plan's explicit constraint (no `fastapi`, `sqlite3`, or `app.portfolio` imports) so it remains independently unit-testable and reusable by plan 03-03's chat endpoint without coupling.
- Imported `litellm.completion` lazily inside `generate_chat_response`'s real-call branch (not at module top level) so importing `app.llm` — and running every mock-mode test — never requires a network stack, package initialization side effects, or an API key.
- The mock directive grammar is documented in the module docstring as a stable contract, since Phase 5's Playwright E2E suite is expected to rely on it to drive deterministic trade/watchlist actions without an OpenRouter key.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required by this plan. Live (non-mock) chat calls will need `OPENROUTER_API_KEY` when plan 03-03 wires the HTTP endpoint; it is documented as already present in the project-root `.env` per PLAN.md §5. All tests in this plan run under `LLM_MOCK=true` or with `litellm.completion` patched, so no key was needed or accessed.

## Next Phase Readiness
`generate_chat_response()`, `ChatResponse`, `TradeIntent`, and `WatchlistChange` are ready for plan 03-03 to wire into the `/api/chat` HTTP endpoint: load portfolio context + chat history, call `generate_chat_response`, auto-execute returned trades/watchlist changes through the existing `app.trade_engine`/watchlist code paths, and persist to `chat_messages`.

---
*Phase: 03-ai-chat-assistant*
*Completed: 2026-07-04*

## Self-Check: PASSED
