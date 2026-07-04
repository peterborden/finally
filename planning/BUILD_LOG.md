# FinAlly Build Log

Append-only coordination log. One bullet per entry, prefixed with your role tag:
`[DB]`, `[BACKEND]`, `[LLM]`, `[FRONTEND]`, `[DEVOPS]`, `[TEST]`.
Record interface changes, cross-module decisions, and "I'm done" status here so
other agents (and the orchestrator merging worktrees) can see them.

See `planning/BUILD_CONTRACT.md` for the authoritative interface contract.

---

- [ORCH] Contract finalized. `uv.lock` refreshed to include `litellm` + `httpx`
  (both were missing). Backend/LLM engineers: run `uv sync --extra dev` first thing
  — it will INSTALL from the committed lock (needs PyPI network; disable sandbox for
  that one command if prompted). Do NOT re-run `uv lock` / change resolutions.
- [ORCH] Each teammate works in an isolated git worktree branched from `agent-teams`.
  Stay strictly within your owned paths (BUILD_CONTRACT §1). Integration happens by the
  orchestrator merging your branch back — keep your branch buildable and tests green.

- [FRONTEND] done — Next.js 14 (14.2.35, patched) + React 18 static-export app (`output: 'export'`) scaffolded in `frontend/`. Tailwind dark terminal theme (accent #ecad0a / blue #209dd7 / purple-submit #753991). All PLAN §10 elements: watchlist (live flash green/red ~500ms via CSS keyframes, SSE-accumulated sparklines, add/remove, click-to-select), Recharts main chart, treemap heatmap (sized by weight, colored by P&L), P&L line chart (/api/portfolio/history), positions table, market-order trade bar, collapsible AI chat panel (POST /api/chat, loading dots, inline trade/watchlist confirmations), header (live total/cash + connection dot). Native EventSource for /api/stream/prices (§5.9 keyed-by-ticker), auto-reconnect status. Null price fields render "—". Same-origin /api/*. 33 Vitest+RTL tests pass; typecheck + `next lint` clean; `next build` emits static export to `frontend/out/` (index.html) — DevOps copies this into backend/static. NOTE: repo-root .gitignore `lib/` rule was silently excluding `frontend/lib/`; re-included via `frontend/.gitignore` negation so the app builds in Docker.

- [DB] done — `backend/app/db/` (schema.sql, connection.py, repositories.py, __init__.py) to CONTRACT §3. 6 tables per PLAN §7, idempotent lazy init + seed. tests/db 30 passed. Additive: exports `get_db_path`; `record_trade` lowercases `side`.
- [BACKEND] done — config.py, main.py `create_app()` factory + lifespan (owns PriceCache/market source on app.state, 30s snapshot loop, db.init_db(), guarded chat.py registration, static SPA fallback after /api), services/{portfolio,watchlist}.py, api/{portfolio,watchlist,health,deps}.py to §4/§5. 45 tests.
- [LLM] done — llm/{schema,prompt,mock,client}.py + api/chat.py (POST /api/chat §5.7). cerebras skill for real call; deterministic mock. 45 tests.
- [DEVOPS] done — multi-stage Dockerfile (node build → python runtime, uv --frozen, frontend/out→/app/static, healthcheck), .dockerignore, docker-compose.yml (finally-data volume), idempotent mac/windows start/stop scripts. Full `docker build` deferred (no Docker in build env).
- [TEST] done — Playwright suite under test/: `api` project (22 tests, §5 contract) + `e2e` project (browser, §10 UI) + docker-compose.test.yml + RUN.md. DOM contract in test/support/selectors.ts.
- [ORCH] Integration: merged all six layers into `agent-teams` (db→backend→llm→frontend→devops→test). NOTE: agents left work uncommitted in worktrees (branch tips at 530eb79); orchestrator committed each layer's owned files (excluding shared BUILD_LOG/pyproject/uv.lock so agent-teams canonical wins). Full backend suite 213 passed against REAL db (no mocks). Assembled app run locally (uvicorn, LLM_MOCK, simulator): health/static/portfolio/watchlist/trade/history/SSE/chat-autoexec all verified; Playwright `api` project 22/22 green vs live server.
- [ORCH] FIX: mock.py trade/watch/remove regexes capped symbol at [A-Za-z]{1,6}, making company-name map entries >6 chars (MICROSOFT, NETFLIX, ALPHABET, FACEBOOK, JPMORGAN) dead code — widened to {1,12}. mock tests still 13/13.
- [ORCH] Cross-worktree gap: browser `e2e` project 23/38 initially — frontend testids didn't match test/support/selectors.ts DOM contract (frontend had `connection-dot`/`chat-actions`; contract expects `connection-status`+data-state/`chat-action` + ~30 others). Reconciling frontend testids to the contract (frontend conforms; tests are fixed).
