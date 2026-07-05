"""Unit tests for the pure trade engine (buy/sell math + validation).

These tests exercise app.trade_engine in isolation -- no DB, no FastAPI,
no market data source. Every case from the plan's <behavior> block is
enumerated explicitly so the average-cost and rejection math is proven
deterministically before it is wired to I/O.
"""

from __future__ import annotations

import pytest

from app.trade_engine import (
    Position,
    Side,
    TradeError,
    TradeResult,
    apply_trade,
)


class TestBuy:
    """Buy-side math: cash decreases, quantity increases, avg_cost blends."""

    def test_buy_fresh_position_sets_avg_cost_to_fill_price(self):
        position = Position(quantity=0.0, avg_cost=0.0)
        result = apply_trade(
            side=Side.BUY, quantity=10, price=100.0, cash=10_000.0, position=position
        )
        assert isinstance(result, TradeResult)
        assert result.new_cash == pytest.approx(9_000.0)
        assert result.new_quantity == pytest.approx(10.0)
        assert result.new_avg_cost == pytest.approx(100.0)
        assert result.remove_position is False
        assert result.filled_quantity == pytest.approx(10.0)
        assert result.filled_price == pytest.approx(100.0)

    def test_buy_into_existing_position_blends_weighted_average(self):
        # 10 @ 100 then 10 @ 200 -> 20 @ 150
        position = Position(quantity=10.0, avg_cost=100.0)
        result = apply_trade(
            side=Side.BUY, quantity=10, price=200.0, cash=10_000.0, position=position
        )
        assert result.new_quantity == pytest.approx(20.0)
        assert result.new_avg_cost == pytest.approx(150.0)
        assert result.new_cash == pytest.approx(10_000.0 - 10 * 200.0)

    def test_buy_fractional_shares_computes_exact_cash_and_avg_cost(self):
        position = Position(quantity=0.0, avg_cost=0.0)
        result = apply_trade(
            side=Side.BUY, quantity=2.5, price=190.32, cash=1_000.0, position=position
        )
        assert result.new_quantity == pytest.approx(2.5)
        assert result.new_avg_cost == pytest.approx(190.32)
        assert result.new_cash == pytest.approx(1_000.0 - 2.5 * 190.32)

    def test_buy_fractional_into_existing_position_blends_correctly(self):
        # 4 @ 50 then 1.5 @ 80 -> 5.5 @ ((4*50 + 1.5*80) / 5.5)
        position = Position(quantity=4.0, avg_cost=50.0)
        result = apply_trade(
            side=Side.BUY, quantity=1.5, price=80.0, cash=10_000.0, position=position
        )
        expected_avg = (4.0 * 50.0 + 1.5 * 80.0) / 5.5
        assert result.new_quantity == pytest.approx(5.5)
        assert result.new_avg_cost == pytest.approx(expected_avg)

    def test_buy_exact_cash_amount_succeeds(self):
        # cash == qty*price exactly -> should succeed, not reject
        position = Position(quantity=0.0, avg_cost=0.0)
        result = apply_trade(
            side=Side.BUY, quantity=10.0, price=100.0, cash=1_000.0, position=position
        )
        assert isinstance(result, TradeResult)
        assert result.new_cash == pytest.approx(0.0)

    def test_buy_with_insufficient_cash_is_rejected_without_mutation(self):
        position = Position(quantity=5.0, avg_cost=90.0)
        with pytest.raises(TradeError) as exc_info:
            apply_trade(
                side=Side.BUY, quantity=100, price=100.0, cash=500.0, position=position
            )
        message = str(exc_info.value)
        assert "cash" in message.lower()
        # Original position must remain untouched by the caller's perspective --
        # apply_trade takes immutable inputs, so simply verify they're unchanged.
        assert position.quantity == pytest.approx(5.0)
        assert position.avg_cost == pytest.approx(90.0)

    def test_buy_insufficient_cash_message_names_shortfall(self):
        with pytest.raises(TradeError) as exc_info:
            apply_trade(
                side=Side.BUY,
                quantity=10,
                price=100.0,
                cash=500.0,
                position=Position(quantity=0.0, avg_cost=0.0),
            )
        message = str(exc_info.value)
        # Shortfall = 1000 - 500 = 500
        assert "500" in message


class TestSell:
    """Sell-side math: cash increases, quantity decreases, avg_cost unchanged."""

    def test_sell_partial_position_preserves_avg_cost(self):
        position = Position(quantity=10.0, avg_cost=100.0)
        result = apply_trade(
            side=Side.SELL, quantity=4, price=120.0, cash=1_000.0, position=position
        )
        assert result.new_cash == pytest.approx(1_000.0 + 4 * 120.0)
        assert result.new_quantity == pytest.approx(6.0)
        assert result.new_avg_cost == pytest.approx(100.0)
        assert result.remove_position is False
        assert result.filled_quantity == pytest.approx(4.0)
        assert result.filled_price == pytest.approx(120.0)

    def test_sell_entire_position_flags_removal(self):
        position = Position(quantity=10.0, avg_cost=100.0)
        result = apply_trade(
            side=Side.SELL, quantity=10.0, price=120.0, cash=0.0, position=position
        )
        assert result.new_quantity == pytest.approx(0.0)
        assert result.remove_position is True

    def test_sell_leaving_epsilon_dust_flags_removal(self):
        # Floating point residue below epsilon should still count as fully sold.
        position = Position(quantity=0.1 + 0.2, avg_cost=50.0)  # 0.30000000000000004
        result = apply_trade(
            side=Side.SELL, quantity=0.3, price=50.0, cash=0.0, position=position
        )
        assert result.remove_position is True
        assert abs(result.new_quantity) < 1e-6

    def test_sell_fractional_leaving_partial_position_keeps_position(self):
        position = Position(quantity=5.0, avg_cost=40.0)
        result = apply_trade(
            side=Side.SELL, quantity=2.5, price=60.0, cash=0.0, position=position
        )
        assert result.new_quantity == pytest.approx(2.5)
        assert result.remove_position is False
        assert result.new_avg_cost == pytest.approx(40.0)

    def test_sell_with_no_position_is_rejected(self):
        position = Position(quantity=0.0, avg_cost=0.0)
        with pytest.raises(TradeError) as exc_info:
            apply_trade(
                side=Side.SELL, quantity=1, price=100.0, cash=0.0, position=position
            )
        message = str(exc_info.value)
        assert "shares" in message.lower() or "position" in message.lower()
        assert position.quantity == pytest.approx(0.0)

    def test_sell_more_than_held_is_rejected_without_mutation(self):
        position = Position(quantity=5.0, avg_cost=100.0)
        with pytest.raises(TradeError):
            apply_trade(
                side=Side.SELL, quantity=10, price=100.0, cash=0.0, position=position
            )
        assert position.quantity == pytest.approx(5.0)
        assert position.avg_cost == pytest.approx(100.0)

    def test_sell_exact_quantity_held_succeeds_and_removes(self):
        position = Position(quantity=3.25, avg_cost=77.0)
        result = apply_trade(
            side=Side.SELL, quantity=3.25, price=80.0, cash=100.0, position=position
        )
        assert result.remove_position is True
        assert result.new_cash == pytest.approx(100.0 + 3.25 * 80.0)


class TestInvalidInput:
    """Zero/negative quantity and non-positive price are rejected outright."""

    @pytest.mark.parametrize("quantity", [0, -1, -0.5])
    def test_buy_rejects_non_positive_quantity(self, quantity):
        with pytest.raises(TradeError):
            apply_trade(
                side=Side.BUY,
                quantity=quantity,
                price=100.0,
                cash=10_000.0,
                position=Position(quantity=0.0, avg_cost=0.0),
            )

    @pytest.mark.parametrize("quantity", [0, -1, -0.5])
    def test_sell_rejects_non_positive_quantity(self, quantity):
        with pytest.raises(TradeError):
            apply_trade(
                side=Side.SELL,
                quantity=quantity,
                price=100.0,
                cash=0.0,
                position=Position(quantity=10.0, avg_cost=50.0),
            )

    @pytest.mark.parametrize("price", [0, -1, -100.0])
    def test_buy_rejects_non_positive_price(self, price):
        with pytest.raises(TradeError):
            apply_trade(
                side=Side.BUY,
                quantity=1,
                price=price,
                cash=10_000.0,
                position=Position(quantity=0.0, avg_cost=0.0),
            )

    @pytest.mark.parametrize("price", [0, -1, -100.0])
    def test_sell_rejects_non_positive_price(self, price):
        with pytest.raises(TradeError):
            apply_trade(
                side=Side.SELL,
                quantity=1,
                price=price,
                cash=0.0,
                position=Position(quantity=10.0, avg_cost=50.0),
            )


class TestPurity:
    """apply_trade must not mutate its inputs regardless of outcome."""

    def test_position_is_frozen(self):
        position = Position(quantity=10.0, avg_cost=100.0)
        with pytest.raises(Exception):
            position.quantity = 5.0  # type: ignore[misc]

    def test_successful_buy_does_not_mutate_input_position(self):
        position = Position(quantity=10.0, avg_cost=100.0)
        apply_trade(side=Side.BUY, quantity=5, price=110.0, cash=10_000.0, position=position)
        assert position.quantity == pytest.approx(10.0)
        assert position.avg_cost == pytest.approx(100.0)

    def test_successful_sell_does_not_mutate_input_position(self):
        position = Position(quantity=10.0, avg_cost=100.0)
        apply_trade(side=Side.SELL, quantity=5, price=110.0, cash=0.0, position=position)
        assert position.quantity == pytest.approx(10.0)
        assert position.avg_cost == pytest.approx(100.0)
