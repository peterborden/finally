"""Tests for PriceUpdate dataclass."""

import pytest

from app.market.models import PriceUpdate


class TestPriceUpdate:
    """Unit tests for the PriceUpdate model."""

    def test_price_update_creation(self):
        """Test basic PriceUpdate creation."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert update.previous_price == 190.00
        assert update.timestamp == 1234567890.0

    def test_change_calculation(self):
        """Test price change calculation."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
        assert update.change == 0.50

    def test_change_negative(self):
        """Test negative price change."""
        update = PriceUpdate(ticker="AAPL", price=189.50, previous_price=190.00, timestamp=1234567890.0)
        assert update.change == -0.50

    def test_change_percent_up(self):
        """Test percentage change calculation (up)."""
        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=100.00, timestamp=1234567890.0)
        assert update.change_percent == 90.0

    def test_change_percent_down(self):
        """Test percentage change calculation (down)."""
        update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=200.00, timestamp=1234567890.0)
        assert update.change_percent == -50.0

    def test_change_percent_zero_previous(self):
        """Test percentage change with zero previous price."""
        update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=0.00, timestamp=1234567890.0)
        assert update.change_percent == 0.0

    def test_direction_up(self):
        """Test direction calculation (up)."""
        update = PriceUpdate(ticker="AAPL", price=191.00, previous_price=190.00, timestamp=1234567890.0)
        assert update.direction == "up"

    def test_direction_down(self):
        """Test direction calculation (down)."""
        update = PriceUpdate(ticker="AAPL", price=189.00, previous_price=190.00, timestamp=1234567890.0)
        assert update.direction == "down"

    def test_direction_flat(self):
        """Test direction calculation (flat)."""
        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=190.00, timestamp=1234567890.0)
        assert update.direction == "flat"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
        result = update.to_dict()

        assert result["ticker"] == "AAPL"
        assert result["price"] == 190.50
        assert result["previous_price"] == 190.00
        assert result["timestamp"] == 1234567890.0
        assert result["change"] == 0.50
        assert result["change_percent"] == 0.2632  # (0.50 / 190.00) * 100
        assert result["direction"] == "up"

    def test_to_dict_includes_daily_fields(self):
        """to_dict exposes the daily-change fields for the watchlist."""
        update = PriceUpdate(
            ticker="AAPL", price=195.00, previous_price=194.50,
            timestamp=1234567890.0, reference_price=190.00,
        )
        result = update.to_dict()
        assert result["reference_price"] == 190.00
        assert result["daily_change"] == 5.00
        assert result["daily_change_percent"] == 2.6316  # (5 / 190) * 100

    def test_daily_change_uses_reference_price(self):
        """daily_change is measured against reference_price, not previous_price."""
        update = PriceUpdate(
            ticker="AAPL", price=195.00, previous_price=194.50, reference_price=190.00,
        )
        assert update.daily_change == 5.00
        assert update.daily_change_percent == 2.6316
        # tick-over-tick change is independent and small
        assert update.change == 0.50

    def test_daily_change_falls_back_to_previous_price(self):
        """Without a reference_price, daily_change mirrors tick-over-tick change."""
        update = PriceUpdate(ticker="AAPL", price=195.00, previous_price=190.00)
        assert update.reference_price is None
        assert update.daily_change == 5.00
        assert update.daily_change_percent == 2.6316

    def test_daily_change_percent_zero_reference(self):
        """A zero reference price yields 0% rather than dividing by zero."""
        update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=50.00, reference_price=0.0)
        assert update.daily_change_percent == 0.0

    def test_immutability(self):
        """Test that PriceUpdate is immutable."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)

        with pytest.raises(AttributeError):
            update.price = 200.00  # Should raise error
