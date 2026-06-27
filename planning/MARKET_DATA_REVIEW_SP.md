# Market Data Backend — Code Review (SP)

**Date:** 2026-06-27
**Reviewer:** Sprite (independent review)
**Scope:** `backend/app/market/` (8 source modules) + `backend/tests/market/` (6 test modules)
**Method:** Read every source/test file, ran the full suite with coverage and lint, and verified the Massive client against the actually-installed `massive` package API.

---

## 0. Resolution Status (updated 2026-06-27)

**All findings below have been fixed.** Post-fix state:

- **Tests:** 93 passed (was 73), **97% coverage** (was 91%), ruff clean, wheel builds, `uv lock --check` passes.
- **H1/H2 (Massive timestamp):** now reads `sip_timestamp` (with `participant_/trf_` fallbacks) and converts from **nanoseconds** (`/1e9`); a missing timestamp falls back to wall-clock instead of discarding the price. `massive_client.py:_trade_timestamp`.
- **Contract test added:** `test_massive.py` now builds snapshots from the **real** `TickerSnapshot.from_dict(...)` model, so attribute/unit drift fails loudly. This test reproduced (and now guards) H1/H2.
- **M1 (normalization):** shared `app/market/utils.py:normalize_ticker` applied consistently across both sources and the simulator core.
- **M2 (SSE):** `stream.py` coverage 33% → 92% via `tests/market/test_stream.py`; `create_stream_router` now builds a fresh `APIRouter` per call.
- **M3 (daily change %):** `PriceUpdate` gained `reference_price` + `daily_change`/`daily_change_percent`; `PriceCache` anchors a session reference (first price seen) and the Massive source supplies prior-day close. Exposed in `to_dict()` / SSE payload.
- **L1:** `PriceCache.version` now reads under the lock.
- **L2:** Massive `add_ticker` polls immediately when live.
- **L3:** `massive` pinned to `>=2.2.0,<3`.

Remaining uncovered lines are inherently runtime-only (infinite poll loop, real REST call, the `StreamingResponse` wrapper, and cancellation handlers). Original findings preserved below for the record.

---

## 1. Executive Summary

The market data subsystem is well-architected and the **simulator path (the default) is solid and correct**. Tests are green, lint is clean, and coverage is high. However, this review found a **High-severity defect in the Massive (real-data) path that is fully masked by the mocked tests**: the code reads a trade timestamp field that does not exist on the real Massive/Polygon model, which would cause *every* price snapshot to be silently skipped when a real `MASSIVE_API_KEY` is supplied. Because the simulator is the documented default, the demo experience is unaffected — but the "real market data" feature, as written, would produce an empty price stream.

**Verdict:** Ship-ready for the simulator-only default. The Massive path needs two fixes (timestamp field name + unit) and a contract test before it can be trusted with a real API key.

---

## 2. Test Results

Ran on Python 3.13.7, `massive==2.2.0` (resolved from `massive>=1.0.0`).

```
73 passed in 3.34s
```

| Metric | Result |
|---|---|
| Tests | **73 passed, 0 failed** |
| Ruff `app/` | Clean |
| Ruff `tests/` | Clean |
| Coverage (overall) | **91%** |

Per-module coverage:

| Module | Cover | Missing |
|---|---|---|
| models.py | 100% | — |
| cache.py | 100% | — |
| interface.py | 100% | — |
| seed_prices.py | 100% | — |
| factory.py | 100% | — |
| simulator.py | 98% | 149 (dup-guard), 268–269 (loop exception log) |
| massive_client.py | 94% | 85–87 (`_poll_loop`), 125 (`_fetch_snapshots`) |
| stream.py | **33%** | 26–48, 62–87 (the entire SSE handler + generator) |

**Note on the prior review:** `planning/archive/MARKET_DATA_REVIEW.md` reported 5 failing tests in `test_massive.py`. Those failures were purely environmental — the `massive` package wasn't installed. With `massive` present (it is a core dependency), **all 5 now pass**. The build-config bug (`[tool.hatch.build.targets.wheel]`) flagged previously is also fixed. Those items are resolved.

---

## 3. Findings

### HIGH

#### H1 — Massive real-data path reads a non-existent timestamp field; all snapshots silently skipped
`backend/app/market/massive_client.py:103`

```python
price     = snap.last_trade.price
timestamp = snap.last_trade.timestamp / 1000.0   # ← AttributeError on the real model
```

The real `massive.rest.models.snapshot.LastTrade` (verified against installed `massive==2.2.0`) exposes:

```
ticker, trf_timestamp, sequence_number, sip_timestamp, participant_timestamp,
conditions, correction, id, price, trf_id, size, exchange, tape
```

There is **no `timestamp` attribute** (`hasattr(LastTrade(), "timestamp") == False`). Accessing `snap.last_trade.timestamp` raises `AttributeError`, which is caught by the `except (AttributeError, TypeError)` block at `massive_client.py:110` — so each snapshot is logged as "Skipping snapshot" and **dropped**. Net effect with a real key: the cache is never populated and the SSE stream emits nothing.

**Why the tests miss it:** `test_massive.py::_make_snapshot` builds a `MagicMock`, and a MagicMock fabricates *any* attribute on access — including `.timestamp`. The mock therefore validates a shape the real API does not have. This is a textbook mock-vs-reality drift.

**Fix:** use `sip_timestamp` (the SIP Unix timestamp) and convert correctly — see H2 for the unit.

#### H2 — Timestamp unit conversion is wrong (nanoseconds, not milliseconds)
`backend/app/market/massive_client.py:103`

Polygon/Massive trade timestamps (`sip_timestamp`) are **Unix nanoseconds**, not milliseconds. The code divides by `1000.0`. Even after fixing the field name (H1), `/1000.0` yields a timestamp ~10^6× too large (year ~50,000+). The divisor should be `1e9`:

```python
timestamp = snap.last_trade.sip_timestamp / 1_000_000_000.0
```

Consider falling back to `participant_timestamp`/`trf_timestamp` (also ns) when `sip_timestamp` is absent, and to `time.time()` as a last resort so a missing timestamp never discards an otherwise-valid price.

### MEDIUM

#### M1 — Ticker normalization differs between the two data sources
`backend/app/market/simulator.py:120-134` vs `massive_client.py:66-76`

`MassiveDataSource.add_ticker`/`remove_ticker` normalize input with `.upper().strip()`. `SimulatorDataSource` / `GBMSimulator` do **not**. The two implementations share one interface (`MarketDataSource`) but behave differently for the same input:

- `add_ticker("aapl")` on the simulator creates a *distinct* ticker `"aapl"` (not `"AAPL"`), and because `SEED_PRICES.get("aapl")` is `None`, it gets a **random price in [50, 300]** (`simulator.py:151`).
- `add_ticker("  AAPL  ")` similarly creates `"  AAPL  "`.

The watchlist API isn't built yet, so normalization could be enforced at that boundary — but the interface contract should be consistent. Recommend normalizing inside `GBMSimulator.add_ticker`/`remove_ticker` (or in `SimulatorDataSource`) to match the Massive client.

#### M2 — SSE endpoint is effectively untested (the primary cache consumer)
`backend/app/market/stream.py` — 33% coverage; lines 26–48 and 62–87 (the route handler and the entire `_generate_events` generator) have no tests.

This is the single most important consumer of `PriceCache` and the contract the frontend depends on, yet there is no integration test. The previous review recommended adding one; it still isn't there. A lightweight `httpx.AsyncClient` test against the FastAPI app could assert: the `retry: 1000` preamble is emitted, a `data: {...}` frame is produced after a cache update, frames are valid JSON matching `PriceUpdate.to_dict()`, and the generator stops on disconnect.

Secondary footgun in the same file: `router` is a **module-level `APIRouter`** (`stream.py:17`) and `create_stream_router()` registers `/prices` onto it via closure. Calling the factory twice (e.g., in tests, or two app instances) double-registers the route on the shared router. Prefer constructing a fresh `APIRouter()` inside the factory.

#### M3 — No "daily change %" reference; only tick-to-tick change is available
`backend/app/market/models.py:23-28`, `cache.py:31-32`

`PLAN.md` (§2, §10) requires the watchlist to show **daily change %**. `PriceUpdate.change` / `change_percent` are computed against the *previous cached tick* (`cache.py:32`: `previous_price = prev.price`), i.e. the change since the last 500ms update — typically sub-cent. There is no daily-open / session-reference price tracked anywhere. Downstream (watchlist/frontend) will have no backend source for "daily change %" as specified. Either track a per-ticker session reference price in the cache/source, or document that daily change must be derived elsewhere (Massive snapshots do carry `todays_change_percent` and `prev_day`, which the simulator would need to emulate).

### LOW

#### L1 — `PriceCache.version` reads `_version` without the lock
`backend/app/market/cache.py:64-67`. Atomic under CPython's GIL today, but inconsistent with every other accessor and a latent race on free-threaded (PEP 703) builds. Trivial to wrap in `with self._lock:`.

#### L2 — Massive `add_ticker` has no immediate seed; new ticker invisible up to `poll_interval`
`backend/app/market/massive_client.py:66-70`. The simulator seeds a new ticker's price into the cache immediately (`simulator.py:246-248`); the Massive client waits for the next poll (up to 15s on the free tier). Inconsistent UX between sources. Consider triggering a one-off `_poll_once()` (or a targeted fetch) on add.

#### L3 — `massive>=1.0.0` is unpinned; API drift is unguarded
`backend/pyproject.toml:11`. The loose lower bound is exactly how H1/H2 can arise: the resolved `2.2.0` model differs from whatever the code was written against. Pin a tested range (e.g. `>=2.2,<3`) and back it with a contract test (see §4).

---

## 4. Recommendations

**Must fix before enabling the Massive path:**
1. H1 — use `sip_timestamp` instead of the non-existent `timestamp`.
2. H2 — divide by `1e9` (nanoseconds), with sensible fallbacks.

**Should fix:**
3. M2 — add at least one SSE integration test and make `create_stream_router` build its own `APIRouter`.
4. M1 — normalize tickers consistently across both sources.
5. Add a **contract test** that builds a real `massive` `TickerSnapshot`/`LastTrade` (or `from_dict` on a recorded fixture) and runs it through `_poll_once`, so attribute/unit drift fails loudly instead of being swallowed by `MagicMock`. This single test would have caught H1 and H2.

**Nice to have:**
6. M3 — provide a backend source for "daily change %" per `PLAN.md`.
7. L1, L2, L3 — minor consistency/robustness cleanups.

---

## 5. What's Done Well

- **Clean strategy/factory architecture** — both sources implement one ABC; `PriceCache` is the single source of truth; downstream is source-agnostic.
- **Correct GBM math** — `exp((mu - 0.5·sigma²)·dt + sigma·√dt·Z)` with a well-reasoned `dt` derived from trading-seconds-per-year; per-ticker sigma/mu are realistically tuned (TSLA 0.50 vs V 0.17).
- **Cholesky-correlated moves** — mathematically sound sector correlation (tech 0.6, finance 0.5, cross/TSLA 0.3), rebuilt on add/remove.
- **`PriceUpdate` is `frozen=True, slots=True`** — immutable, memory-efficient, with a clean `to_dict()` for SSE.
- **Defensive long-running loops** — both the simulator loop and the Massive poller catch and log exceptions and keep running; tasks are cancellable and `stop()` is idempotent.
- **SSE design** — version-based change detection avoids redundant payloads; `retry: 1000` enables browser auto-reconnect; nginx buffering disabled via `X-Accel-Buffering: no`.
- **Thread-safe cache** — `Lock`-guarded mutations, correct given the Massive client runs API calls via `asyncio.to_thread`.
- **Tests, lint, coverage** — 73 green, ruff clean, 91% overall; the simulator and cache are thoroughly covered (98–100%).
- **The Massive REST call itself is correct** — `get_snapshot_all(market_type=SnapshotMarketType.STOCKS, tickers=...)` matches the installed package signature; only the response *parsing* (H1/H2) is wrong.

---

## 6. How to Reproduce

```bash
cd backend
uv sync --extra dev
uv run --extra dev pytest -v --cov=app --cov-report=term-missing
uv run --extra dev ruff check app/ tests/

# Verify H1/H2 against the real model:
uv run python -c "from massive.rest.models.snapshot import LastTrade; \
print('has timestamp:', hasattr(LastTrade(), 'timestamp')); \
print('has sip_timestamp:', hasattr(LastTrade(), 'sip_timestamp'))"
# -> has timestamp: False  /  has sip_timestamp: True
```
