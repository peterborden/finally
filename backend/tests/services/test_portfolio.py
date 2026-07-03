"""Unit tests for the portfolio service: trade math + state assembly."""

from __future__ import annotations

import pytest

from app.market.cache import PriceCache
from app.services import portfolio as svc
from tests.services.fakes import FakeDB


@pytest.fixture
def cache() -> PriceCache:
    c = PriceCache()
    c.update("AAPL", 190.0)
    c.update("MSFT", 420.0)
    return c


@pytest.fixture
def patch_db(monkeypatch):
    """Return a helper that installs a FakeDB into the service module."""

    def _install(fake: FakeDB) -> FakeDB:
        monkeypatch.setattr(svc, "db", fake)
        return fake

    return _install


# --------------------------- BUY ---------------------------

def test_buy_success_updates_cash_position_trade_snapshot(cache, patch_db):
    fake = patch_db(FakeDB(cash=10000.0))
    result = svc.execute_trade("AAPL", "buy", 10, cache)

    assert result.success is True
    assert result.error is None
    assert result.cash_balance == pytest.approx(8100.0)  # 10000 - 10*190
    assert result.position["quantity"] == pytest.approx(10)
    assert result.position["avg_cost"] == pytest.approx(190.0)
    assert result.trade["side"] == "buy"
    assert result.trade["price"] == pytest.approx(190.0)
    # A snapshot was recorded as part of the trade transaction.
    assert fake.get_snapshots(None)[-1]["total_value"] == pytest.approx(10000.0)


def test_buy_lowercase_and_whitespace_ticker_normalized(cache, patch_db):
    patch_db(FakeDB(cash=10000.0))
    result = svc.execute_trade("  aapl ", "BUY", 1, cache)
    assert result.success is True
    assert result.trade["ticker"] == "AAPL"


def test_buy_weighted_average_cost(cache, patch_db):
    patch_db(FakeDB(cash=100000.0))
    svc.execute_trade("AAPL", "buy", 10, cache)  # @190
    cache.update("AAPL", 200.0)
    result = svc.execute_trade("AAPL", "buy", 10, cache)  # @200
    assert result.position["quantity"] == pytest.approx(20)
    assert result.position["avg_cost"] == pytest.approx(195.0)  # (1900+2000)/20


def test_buy_insufficient_cash_fails_without_mutation(cache, patch_db):
    fake = patch_db(FakeDB(cash=100.0))
    result = svc.execute_trade("AAPL", "buy", 10, cache)  # needs 1900
    assert result.success is False
    assert result.error == "Insufficient cash: need $1900.00, have $100.00"
    assert result.cash_balance == pytest.approx(100.0)
    assert fake.get_position(None, "AAPL") is None
    assert fake.get_trades(None) == []


def test_buy_exact_cash_allowed(cache, patch_db):
    patch_db(FakeDB(cash=1900.0))
    result = svc.execute_trade("AAPL", "buy", 10, cache)
    assert result.success is True
    assert result.cash_balance == pytest.approx(0.0)


# --------------------------- SELL ---------------------------

def test_sell_partial_reduces_position_keeps_avg(cache, patch_db):
    patch_db(FakeDB(cash=1000.0, positions={"AAPL": (10, 150.0)}))
    result = svc.execute_trade("AAPL", "sell", 4, cache)  # @190
    assert result.success is True
    assert result.cash_balance == pytest.approx(1760.0)  # 1000 + 4*190
    assert result.position["quantity"] == pytest.approx(6)
    assert result.position["avg_cost"] == pytest.approx(150.0)


def test_sell_all_deletes_position(cache, patch_db):
    fake = patch_db(FakeDB(cash=0.0, positions={"AAPL": (10, 150.0)}))
    result = svc.execute_trade("AAPL", "sell", 10, cache)
    assert result.success is True
    assert result.position is None
    assert fake.get_position(None, "AAPL") is None
    assert result.cash_balance == pytest.approx(1900.0)


def test_oversell_fails(cache, patch_db):
    patch_db(FakeDB(cash=0.0, positions={"AAPL": (5, 150.0)}))
    result = svc.execute_trade("AAPL", "sell", 20, cache)
    assert result.success is False
    assert "Insufficient shares" in result.error
    assert result.cash_balance == pytest.approx(0.0)


def test_sell_with_no_position_fails(cache, patch_db):
    patch_db(FakeDB(cash=0.0))
    result = svc.execute_trade("AAPL", "sell", 1, cache)
    assert result.success is False
    assert "Insufficient shares" in result.error


# --------------------------- VALIDATION ---------------------------

@pytest.mark.parametrize("qty", [0, -5, -0.001])
def test_non_positive_quantity_fails(cache, patch_db, qty):
    patch_db(FakeDB(cash=10000.0))
    result = svc.execute_trade("AAPL", "buy", qty, cache)
    assert result.success is False
    assert result.error == "Quantity must be positive"


def test_no_price_available_fails(cache, patch_db):
    patch_db(FakeDB(cash=10000.0))
    result = svc.execute_trade("TSLA", "buy", 1, cache)  # not in cache
    assert result.success is False
    assert result.error == "No price available for TSLA"


def test_invalid_side_fails(cache, patch_db):
    patch_db(FakeDB(cash=10000.0))
    result = svc.execute_trade("AAPL", "hold", 1, cache)
    assert result.success is False
    assert "Invalid side" in result.error


def test_fractional_shares_supported(cache, patch_db):
    patch_db(FakeDB(cash=10000.0))
    result = svc.execute_trade("AAPL", "buy", 2.5, cache)
    assert result.success is True
    assert result.position["quantity"] == pytest.approx(2.5)
    assert result.cash_balance == pytest.approx(10000.0 - 2.5 * 190.0)


# --------------------------- PORTFOLIO STATE ---------------------------

def test_get_portfolio_state_shape_and_math(cache, patch_db):
    patch_db(FakeDB(cash=8100.0, positions={"AAPL": (10, 190.0)}))
    state = svc.get_portfolio_state(cache)
    assert state["cash_balance"] == pytest.approx(8100.0)
    assert state["positions_value"] == pytest.approx(1900.0)
    assert state["total_value"] == pytest.approx(10000.0)
    assert state["total_unrealized_pnl"] == pytest.approx(0.0)
    pos = state["positions"][0]
    assert set(pos) == {
        "ticker", "quantity", "avg_cost", "current_price",
        "market_value", "unrealized_pnl", "unrealized_pnl_percent",
    }
    assert pos["current_price"] == pytest.approx(190.0)


def test_get_portfolio_state_unrealized_pnl(cache, patch_db):
    patch_db(FakeDB(cash=0.0, positions={"AAPL": (10, 180.0)}))
    cache.update("AAPL", 190.0)
    state = svc.get_portfolio_state(cache)
    pos = state["positions"][0]
    assert pos["unrealized_pnl"] == pytest.approx(100.0)  # (190-180)*10
    assert pos["unrealized_pnl_percent"] == pytest.approx(5.56, abs=0.01)


def test_get_portfolio_state_null_price_contributes_zero(patch_db):
    empty_cache = PriceCache()  # no prices at all
    patch_db(FakeDB(cash=5000.0, positions={"AAPL": (10, 180.0)}))
    state = svc.get_portfolio_state(empty_cache)
    pos = state["positions"][0]
    assert pos["current_price"] is None
    assert pos["market_value"] == 0.0
    assert pos["unrealized_pnl"] == 0.0
    assert state["positions_value"] == 0.0
    assert state["total_value"] == pytest.approx(5000.0)


# --------------------------- SNAPSHOT ---------------------------

def test_record_portfolio_snapshot(cache, patch_db):
    fake = patch_db(FakeDB(cash=8100.0, positions={"AAPL": (10, 190.0)}))
    snap = svc.record_portfolio_snapshot(cache)
    assert snap["total_value"] == pytest.approx(10000.0)
    assert fake.get_snapshots(None)[-1]["total_value"] == pytest.approx(10000.0)


def test_get_history_returns_snapshots(patch_db):
    fake = patch_db(FakeDB())
    fake.record_snapshot(None, 10000.0)
    fake.record_snapshot(None, 10500.0)
    history = svc.get_history()
    assert [s["total_value"] for s in history] == [10000.0, 10500.0]
