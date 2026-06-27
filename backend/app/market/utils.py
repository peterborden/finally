"""Small shared helpers for the market data subsystem."""

from __future__ import annotations


def normalize_ticker(ticker: str) -> str:
    """Canonical form of a ticker symbol: stripped and uppercased.

    Both data sources and the cache use this so that "aapl", " AAPL ", and
    "AAPL" always resolve to the same symbol regardless of source.
    """
    return ticker.strip().upper()
