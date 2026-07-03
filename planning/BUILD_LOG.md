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
