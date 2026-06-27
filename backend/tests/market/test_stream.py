"""Tests for the SSE streaming endpoint."""

import json
from types import SimpleNamespace

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class FakeRequest:
    """Minimal stand-in for starlette's Request for the SSE generator.

    Reports connected for `connected_polls` disconnect checks, then disconnected
    so the generator's loop terminates.
    """

    def __init__(self, connected_polls: int = 1, host: str | None = "1.2.3.4"):
        self._calls = 0
        self._connected_polls = connected_polls
        self.client = SimpleNamespace(host=host) if host is not None else None

    async def is_disconnected(self) -> bool:
        self._calls += 1
        return self._calls > self._connected_polls


async def _collect(agen) -> list[str]:
    frames = []
    async for frame in agen:
        frames.append(frame)
    return frames


@pytest.mark.asyncio
class TestStream:
    async def test_emits_retry_preamble(self):
        """The stream opens with an SSE retry directive for auto-reconnect."""
        cache = PriceCache()
        frames = await _collect(_generate_events(cache, FakeRequest(connected_polls=0), interval=0))
        assert frames[0] == "retry: 1000\n\n"

    async def test_emits_data_frame_with_prices(self):
        """A populated cache produces a valid SSE data frame of PriceUpdate dicts."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        frames = await _collect(_generate_events(cache, FakeRequest(connected_polls=1), interval=0))

        data_frames = [f for f in frames if f.startswith("data: ")]
        assert len(data_frames) == 1

        payload = json.loads(data_frames[0][len("data: ") :].strip())
        assert "AAPL" in payload
        assert payload["AAPL"]["price"] == 190.50
        # Carries the daily-change fields the watchlist needs
        assert "daily_change_percent" in payload["AAPL"]
        assert payload["AAPL"]["direction"] == "flat"

    async def test_no_data_frame_when_cache_empty(self):
        """An empty cache yields only the retry preamble, no data frames."""
        cache = PriceCache()
        frames = await _collect(_generate_events(cache, FakeRequest(connected_polls=2), interval=0))
        assert all(not f.startswith("data: ") for f in frames)

    async def test_only_sends_on_version_change(self):
        """Unchanged cache version does not re-emit the same payload every tick."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        # Stay "connected" for several polls but never change the cache
        frames = await _collect(_generate_events(cache, FakeRequest(connected_polls=4), interval=0))
        data_frames = [f for f in frames if f.startswith("data: ")]
        assert len(data_frames) == 1  # Sent once, then suppressed until version changes

    async def test_handles_missing_client(self):
        """A request with no client info still streams (host logged as unknown)."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        req = FakeRequest(connected_polls=1, host=None)
        frames = await _collect(_generate_events(cache, req, interval=0))
        assert any(f.startswith("data: ") for f in frames)

    async def test_factory_builds_independent_routers(self):
        """Each create_stream_router call returns a fresh router (no shared state)."""
        cache = PriceCache()
        r1 = create_stream_router(cache)
        r2 = create_stream_router(cache)
        assert r1 is not r2
        paths = {route.path for route in r1.routes}
        assert "/api/stream/prices" in paths
        # Each router registers the route exactly once
        assert sum(1 for route in r2.routes if route.path == "/api/stream/prices") == 1
