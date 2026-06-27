"""Tests for MassiveDataSource.

Snapshots are built from the *real* massive model classes via ``from_dict``
(not bare MagicMocks) so that attribute/unit drift in the Massive API surfaces
as a test failure instead of being silently swallowed by a fabricated mock.
"""

from unittest.mock import patch

import pytest
from massive.rest.models.snapshot import TickerSnapshot

from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def _make_snapshot(
    ticker: str,
    price: float,
    timestamp_ns: int,
    prev_close: float | None = None,
) -> TickerSnapshot:
    """Build a real TickerSnapshot the way the Massive REST API would return it.

    Polygon/Massive payload keys: lastTrade.p (price), lastTrade.t (ns SIP
    timestamp), prevDay.c (prior-day close).
    """
    payload: dict = {"ticker": ticker, "lastTrade": {"p": price, "t": timestamp_ns}}
    if prev_close is not None:
        payload["prevDay"] = {"c": prev_close}
    return TickerSnapshot.from_dict(payload)


@pytest.mark.asyncio
class TestMassiveDataSource:
    """Unit tests for MassiveDataSource with real-model snapshots."""

    async def test_poll_updates_cache(self):
        """Polling writes the last-trade price into the cache."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "GOOGL"]
        source._client = object()  # Satisfy the _poll_once guard

        mock_snapshots = [
            _make_snapshot("AAPL", 190.50, 1707580800000000000),
            _make_snapshot("GOOGL", 175.25, 1707580800000000000),
        ]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_malformed_snapshot_skipped(self):
        """A snapshot with no last-trade price is skipped, not fatal."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "BAD"]
        source._client = object()

        good = _make_snapshot("AAPL", 190.50, 1707580800000000000)
        no_trade = TickerSnapshot.from_dict({"ticker": "BAD"})  # no lastTrade at all
        no_price = TickerSnapshot.from_dict({"ticker": "NOPX", "lastTrade": {"t": 123}})  # price None

        with patch.object(source, "_fetch_snapshots", return_value=[good, no_trade, no_price]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None
        assert cache.get_price("NOPX") is None

    async def test_api_error_does_not_crash(self):
        """API errors are swallowed so the poll loop keeps running."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = object()

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()  # Should not raise

        assert cache.get_price("AAPL") is None  # No update happened

    async def test_timestamp_conversion_nanoseconds_to_seconds(self):
        """SIP timestamps (Unix nanoseconds) are converted to Unix seconds."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = object()

        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000000000)]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        assert update.timestamp == 1707580800.0  # ns / 1e9

    async def test_prev_day_close_used_as_daily_reference(self):
        """Prior-day close populates the daily-change reference price."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = object()

        snap = _make_snapshot("AAPL", 190.50, 1707580800000000000, prev_close=188.0)
        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        assert update.reference_price == 188.0
        assert update.daily_change == 2.5

    async def test_missing_timestamp_falls_back_to_walltime(self):
        """A snapshot with a price but no timestamp still updates (no discard)."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = object()

        snap = TickerSnapshot.from_dict({"ticker": "AAPL", "lastTrade": {"p": 190.5}})
        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.5  # price kept despite missing ts

    async def test_add_ticker(self):
        """Adding a ticker registers it in the active set."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.add_ticker("AAPL")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_uppercase_normalization(self):
        """Tickers are normalized to uppercase."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.add_ticker("aapl")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_strips_whitespace(self):
        """Ticker whitespace is stripped."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.add_ticker("  AAPL  ")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_polls_immediately_when_running(self):
        """When the client is live, adding a ticker triggers an immediate poll."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = object()

        snap = _make_snapshot("TSLA", 250.0, 1707580800000000000)
        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source.add_ticker("tsla")

        assert cache.get_price("TSLA") == 250.0

    async def test_remove_ticker(self):
        """Removing a ticker drops it from the set and the cache."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "GOOGL"]
        cache.update("AAPL", 190.00)

        await source.remove_ticker("AAPL")
        assert "AAPL" not in source.get_tickers()
        assert cache.get("AAPL") is None

    async def test_get_tickers(self):
        """get_tickers returns a copy of the active set."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "GOOGL"]

        tickers = source.get_tickers()
        assert tickers == ["AAPL", "GOOGL"]

    async def test_empty_tickers_skips_poll(self):
        """Polling is skipped when there are no tickers."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = []
        source._client = object()

        with patch.object(source, "_fetch_snapshots") as mock_fetch:
            await source._poll_once()
            mock_fetch.assert_not_called()

    async def test_stop_is_idempotent(self):
        """stop() can be called repeatedly."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.stop()
        await source.stop()  # Should not raise

    async def test_stop_cancels_task(self):
        """stop() cancels the polling task."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=10.0)

        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[]):
                await source.start(["AAPL"])

        assert source._task is not None
        assert not source._task.done()

        await source.stop()
        assert source._task is None

    async def test_start_immediate_poll(self):
        """start() does an immediate poll before entering the loop."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000000000)]

        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
                await source.start(["AAPL"])

        assert cache.get_price("AAPL") == 190.50

        await source.stop()

    async def test_start_normalizes_tickers(self):
        """start() normalizes its initial ticker list."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[]):
                await source.start(["aapl", "  googl "])

        assert source.get_tickers() == ["AAPL", "GOOGL"]
        await source.stop()
