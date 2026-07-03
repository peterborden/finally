# RUN.md — Orchestrator run instructions for the E2E suite

Follow this **after** merging all engineer worktrees (frontend, backend, db, llm, docker)
into the integration branch so the full app + `Dockerfile` exist alongside `test/`.

## Preconditions (must be true post-merge)

- [ ] Repo root `Dockerfile` builds the assembled app (Node build → Python runtime,
      frontend static export copied into `backend/static/`), listening on `:8000`.
- [ ] Backend serves all `/api/*` routes from BUILD_CONTRACT §5 and the SSE stream §5.9.
- [ ] Frontend adds the `data-testid` attributes listed in `test/support/selectors.ts`
      (see the `[TEST]` request in `planning/BUILD_LOG.md`). Without them the `e2e`
      project falls back to text selectors (looser, may be flaky) but should still run.
- [ ] App honors `LLM_MOCK=true` (deterministic chat, parses "buy N TICKER") and uses
      the market **simulator** when `MASSIVE_API_KEY` is empty.

## Option A — Containerized (recommended, hermetic)

```bash
# from repo root
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

- Builds `finally:test` from the root `Dockerfile`.
- Starts `app` with `LLM_MOCK=true`, empty `MASSIVE_API_KEY`, fresh DB volume.
- Waits for `app` `/api/health` to be healthy, then runs the whole suite against
  `http://app:8000`.
- **Exit code** of the `playwright` service = suite result (0 = all green).
- HTML report + traces land in `test/playwright-report/` and `test/test-results/`.

Teardown (drops the ephemeral DB volume so the next run is pristine):

```bash
docker compose -f test/docker-compose.test.yml down -v
```

## Option B — Local app + local Playwright

```bash
# 1. Start the app however DevOps documents (e.g. scripts/start_mac.sh), with:
#    LLM_MOCK=true  MASSIVE_API_KEY=  ->  http://localhost:8000
# 2. Run the suite:
cd test
npm install
npx playwright install --with-deps chromium
BASE_URL=http://localhost:8000 npx playwright test
```

Run subsets:

```bash
BASE_URL=http://localhost:8000 npx playwright test --project=api   # contract only (no browser)
BASE_URL=http://localhost:8000 npx playwright test --project=e2e   # UI only
npx playwright test e2e/03-trade.spec.ts                           # single file
npx playwright show-report                                         # open last HTML report
```

## Expected results (all green)

| Area | Assertions |
|---|---|
| `api/01` | health `{status:"ok"}`; portfolio §5.1 shape & `total = cash + positions`; 10 seed tickers §5.4 |
| `api/02` | add → 201 §5.4 item; uppercase normalization; delete → `{removed:true}`; absent → 404 |
| `api/03` | buy 200 §5.2 (cash↓, position appears); sell 200 (cash↑, position gone); insufficient cash → 400; oversell → 400; qty 0 → 400 |
| `api/04` | history `{snapshots:[{total_value,recorded_at}]}`; grows on trade; chronological |
| `api/05` | chat §5.7 shape; "buy 4 AAPL" executes & reflects in portfolio; big buy → `errors[]` not `trades[]` |
| `api/06` | SSE payload keyed by ticker §5.9; prices move across the window |
| `e2e/01` | terminal loads; 10 tickers; $10k; streaming prices; connected dot |
| `e2e/02` | add/remove ticker via UI |
| `e2e/03` | buy: cash↓ + position row; sell: cash↑ + row gone |
| `e2e/04` | heatmap tiles (colored) + positions table + P&L chart has points |
| `e2e/05` | chat reply + inline trade execution reflected in portfolio |
| `e2e/06` | offline → indicator degrades → back online → reconnect → prices resume |

> The `$10,000 / no positions` fresh-start assertion (`api/01`, `e2e/01` cash) is exact
> only against a **fresh DB volume**. Option A guarantees that. For repeated Option B
> runs, either recreate the DB or accept the invariant-based fallbacks the specs use.

## Triage on failure

- Open `test/playwright-report/index.html` — traces, screenshots, and video for each
  failed `e2e` test are attached (`trace: retain-on-failure`).
- A failing `api` project points at a backend/contract mismatch (check the asserted §5
  shape in the spec vs. the actual response).
- A failing `e2e` test with a "testid missing" annotation → Frontend needs to add the
  requested `data-testid` (see `test/support/selectors.ts`).
