---
phase: 03-ai-chat-assistant
plan: 01
subsystem: infra
tags: [litellm, pydantic, uv, dependencies, openrouter, cerebras]

# Dependency graph
requires:
  - phase: 02-portfolio-trading
    provides: backend/pyproject.toml uv project with FastAPI, numpy, massive, rich deps
provides:
  - litellm and pydantic declared as explicit backend runtime dependencies
  - resolved uv.lock enabling `from litellm import completion` in app code
affects: [03-02 (app/llm.py wrapper), 03-03 (chat endpoint)]

# Tech tracking
tech-stack:
  added: [litellm>=1.0.0, pydantic>=2.0.0]
  patterns: []

key-files:
  created: []
  modified: [backend/pyproject.toml, backend/uv.lock]

key-decisions:
  - "litellm and pydantic added as runtime deps (not dev-only) since the chat endpoint is production code"
  - "Supply-chain human-verify checkpoint pre-approved by user before execution (litellm/pydantic are the exact packages mandated by the checked-in cerebras-inference skill)"

patterns-established: []

requirements-completed: [CHAT-02]

coverage:
  - id: D1
    description: "litellm and pydantic declared in backend/pyproject.toml and resolved into uv.lock, importable via uv run"
    requirement: "CHAT-02"
    verification:
      - kind: unit
        ref: "uv run python -c \"import litellm, pydantic; print('ok')\""
        status: pass
    human_judgment: false

# Metrics
duration: 5min
completed: 2026-07-04
status: complete
---

# Phase 3 Plan 1: LiteLLM Dependency Provisioning Summary

**Added litellm and pydantic as explicit backend runtime dependencies, resolved via uv sync, gated by a pre-approved supply-chain legitimacy checkpoint**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2 (1 checkpoint, 1 auto)
- **Files modified:** 2

## Accomplishments
- `litellm>=1.0.0` and `pydantic>=2.0.0` added to `[project].dependencies` in `backend/pyproject.toml`
- `uv sync --extra dev` regenerated `backend/uv.lock`, resolving litellm 1.91.0 and 35 transitive packages (openai SDK, tiktoken, aiohttp, etc.)
- `import litellm, pydantic` succeeds in the backend uv environment
- Full backend test suite (131 tests) still passes after the dependency addition

## Task Commits

1. **Task 1: Verify litellm + pydantic package legitimacy (supply-chain gate)** - pre-approved by user in the executor prompt (no separate commit; checkpoint gate, no code change)
2. **Task 2: Add litellm + pydantic to pyproject.toml and sync (CHAT-02)** - `8eb140d` (feat)

**Plan metadata:** committed with final phase-level docs commit (see combined report)

## Files Created/Modified
- `backend/pyproject.toml` - added litellm and pydantic to runtime dependencies
- `backend/uv.lock` - regenerated lockfile resolving litellm 1.91.0 + transitive deps

## Decisions Made
- Declared both packages as runtime (not dev) dependencies since `app/llm.py` (plan 03-02) and the chat endpoint (plan 03-03) are production code paths, not test-only.
- The Task 1 human-verify checkpoint (`gate="blocking-human"`) was pre-approved by the user in the orchestrator prompt: litellm is the exact package the project's own `.claude/skills/cerebras/SKILL.md` mandates for the LiteLLM → OpenRouter → Cerebras call path, so the install proceeded without an interactive pause.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required by this plan. (Live, non-mock chat calls will need `OPENROUTER_API_KEY`, already documented as present in the project-root `.env` per PLAN.md §5; tests use `LLM_MOCK=true` and don't need it.)

## Next Phase Readiness
`litellm` and `pydantic` are importable in the backend uv environment, unblocking plan 03-02 (`app/llm.py` wrapper implementing the structured-output schema, prompt builder, and mock/real call paths).

---
*Phase: 03-ai-chat-assistant*
*Completed: 2026-07-04*

## Self-Check: PASSED
