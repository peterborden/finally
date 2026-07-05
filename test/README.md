# FinAlly E2E Suite

Playwright tests exercising the containerized `finally` app end-to-end,
always under `LLM_MOCK=true` so `/api/chat` is deterministic and no
`OPENROUTER_API_KEY` is required.

Covers the PLAN.md §12 scenarios: fresh start, add/remove a watchlist
ticker, buy shares, sell shares, portfolio visualizations rendering, a
mocked AI chat driving a trade inline, and SSE reconnect resilience.

First-run browser download and image build can each take several minutes.

## Option A: docker compose (fully containerized)

From the repo root:

```bash
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

This builds the root `Dockerfile` image, starts it with `LLM_MOCK=true`
on an ephemeral database volume, waits for `/api/health` to report
healthy, then runs the Playwright suite against it inside the official
`mcr.microsoft.com/playwright` runner image (`E2E_BASE_URL=http://app:8000`
is set automatically). Tear down with:

```bash
docker compose -f test/docker-compose.test.yml down -v
```

## Option B: local (faster iteration)

Start the app container once:

```bash
docker run -d --name finally-e2e -p 8000:8000 -e LLM_MOCK=true finally
```

Wait for it to become healthy (`curl http://localhost:8000/api/health`
should return `{"status":"ok"}`), then from `test/`:

```bash
cd test
npm install
npx playwright install --with-deps chromium   # first run only
E2E_BASE_URL=http://localhost:8000 npx playwright test
```

Tear down:

```bash
docker rm -f finally-e2e
```

## Notes

- `playwright.config.ts` does not start the app itself (no `webServer`) --
  point it at a running container via `E2E_BASE_URL`, or accept the
  `http://localhost:8000` default.
- Retries are disabled; every scenario is expected to be deterministic
  under `LLM_MOCK=true`.
