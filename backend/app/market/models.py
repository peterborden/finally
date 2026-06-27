"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time.

    Two notions of "change" are exposed:
      - ``change`` / ``change_percent``: tick-over-tick, vs the previous update.
        Useful for the green/red flash animation on each price move.
      - ``daily_change`` / ``daily_change_percent``: vs ``reference_price``, the
        session/day reference (e.g. the first price seen this session, or the
        prior-day close supplied by a real data source). This is the figure the
        watchlist shows as "daily change %". Falls back to ``previous_price``
        when no reference is set.
    """

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds
    reference_price: float | None = None  # Session/day reference for daily change

    @property
    def change(self) -> float:
        """Absolute price change from the previous update (tick-over-tick)."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from the previous update (tick-over-tick)."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def _reference(self) -> float:
        """Reference price for daily change, falling back to previous_price."""
        return self.reference_price if self.reference_price is not None else self.previous_price

    @property
    def daily_change(self) -> float:
        """Absolute price change from the session/day reference price."""
        return round(self.price - self._reference, 4)

    @property
    def daily_change_percent(self) -> float:
        """Percentage change from the session/day reference price."""
        ref = self._reference
        if ref == 0:
            return 0.0
        return round((self.price - ref) / ref * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "reference_price": self.reference_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "daily_change": self.daily_change,
            "daily_change_percent": self.daily_change_percent,
            "direction": self.direction,
        }
