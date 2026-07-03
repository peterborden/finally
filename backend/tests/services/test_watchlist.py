"""Unit tests for the watchlist service (DB + market source sync)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.market.cache import PriceCache
from app.services import watchlist as svc
from tests.services.fakes import FakeDB


@pytest.fixture
def patch_db(monkeypatch):
    def _install(fake: FakeDB) -> FakeDB:
        monkeypatch.setattr(svc, "db", fake)
        return fake

    return _install


async def test_add_ticker_persists_and_tracks(patch_db):
    fake = patch_db(FakeDB())
    source = AsyncMock()
    row = await svc.add_ticker("pypl", source, PriceCache())
    assert row["ticker"] == "PYPL"
    source.add_ticker.assert_awaited_once_with("PYPL")
    assert [r["ticker"] for r in fake.get_watchlist(None)] == ["PYPL"]


async def test_add_ticker_idempotent(patch_db):
    fake = patch_db(FakeDB())
    source = AsyncMock()
    await svc.add_ticker("AAPL", source, None)
    await svc.add_ticker("AAPL", source, None)
    assert [r["ticker"] for r in fake.get_watchlist(None)] == ["AAPL"]


async def test_remove_ticker_present(patch_db):
    fake = patch_db(FakeDB())
    fake.add_watchlist_ticker(None, "AAPL")
    source = AsyncMock()
    removed = await svc.remove_ticker("aapl", source)
    assert removed is True
    source.remove_ticker.assert_awaited_once_with("AAPL")
    assert fake.get_watchlist(None) == []


async def test_remove_ticker_absent_returns_false(patch_db):
    patch_db(FakeDB())
    source = AsyncMock()
    removed = await svc.remove_ticker("ZZZZ", source)
    assert removed is False
    # Source is still asked to stop tracking (no-op if not present).
    source.remove_ticker.assert_awaited_once_with("ZZZZ")


def test_get_watchlist_with_prices(patch_db):
    fake = patch_db(FakeDB())
    fake.add_watchlist_ticker(None, "AAPL")
    fake.add_watchlist_ticker(None, "MSFT")
    cache = PriceCache()
    cache.update("AAPL", 190.0, reference_price=188.0)
    # MSFT has no price yet.
    items = svc.get_watchlist(cache)
    by_ticker = {i["ticker"]: i for i in items}

    aapl = by_ticker["AAPL"]
    assert aapl["price"] == pytest.approx(190.0)
    assert aapl["previous_price"] == pytest.approx(188.0)
    assert aapl["change"] == pytest.approx(2.0)
    assert aapl["direction"] in {"up", "down", "flat"}

    msft = by_ticker["MSFT"]
    assert msft["price"] is None
    assert msft["change"] is None
    assert msft["direction"] is None


def test_watchlist_item_shape():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    item = svc.watchlist_item("AAPL", cache)
    assert set(item) == {
        "ticker", "price", "previous_price", "change", "change_percent", "direction",
    }
