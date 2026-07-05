"""Tests for the periodic portfolio snapshot background task (PORT-06, periodic half).

Drives the app lifespan with SNAPSHOT_INTERVAL_SECONDS set low enough that
several periodic ticks fire during a fast test, proving the background
task -- independent of any trade -- accumulates portfolio_snapshots rows
over time and cancels cleanly on shutdown. The immediate post-trade half
of PORT-06 is covered separately in test_portfolio.py.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class TestSnapshotRecorder:
    """Integration tests for the periodic snapshot background task."""

    @pytest.fixture
    def db_path(self, tmp_path, monkeypatch):
        """Point FINALLY_DB_PATH at an isolated tmp_path file for this test."""
        path = tmp_path / "finally.db"
        monkeypatch.setenv("FINALLY_DB_PATH", str(path))
        return path

    @pytest.fixture
    def short_interval(self, monkeypatch):
        """Drive the periodic task at a small interval so the test is fast."""
        interval = 0.05
        monkeypatch.setenv("SNAPSHOT_INTERVAL_SECONDS", str(interval))
        return interval

    def test_periodic_snapshots_accumulate_without_a_trade(self, db_path, short_interval):
        """The background task records snapshots over time with no trade (PORT-06)."""
        app = create_app()

        with TestClient(app) as client:
            client.app.state.price_cache.update("AAPL", 100.0)

            # First request lazily initializes the DB. The recorder sleeps
            # before its first tick, so this always wins the race.
            response = client.get("/api/health")
            assert response.status_code == 200

            first_count = len(client.get("/api/portfolio/history").json())

            deadline = time.monotonic() + 2.0
            grown = False
            while time.monotonic() < deadline:
                time.sleep(short_interval * 2)
                rows = client.get("/api/portfolio/history").json()
                if len(rows) > first_count:
                    grown = True
                    break

            assert grown, "expected periodic snapshots to accumulate without a trade"

        # The `with` block above exited without raising, proving the
        # lifespan shutdown cancelled and awaited the background task
        # cleanly (T-02-11).

    def test_invalid_interval_falls_back_to_default(self, monkeypatch):
        """A non-positive/invalid SNAPSHOT_INTERVAL_SECONDS falls back safely (T-02-12)."""
        from app.snapshots import DEFAULT_INTERVAL_SECONDS, _resolve_interval

        monkeypatch.setenv("SNAPSHOT_INTERVAL_SECONDS", "-5")
        assert _resolve_interval() == DEFAULT_INTERVAL_SECONDS

        monkeypatch.setenv("SNAPSHOT_INTERVAL_SECONDS", "not-a-number")
        assert _resolve_interval() == DEFAULT_INTERVAL_SECONDS

        monkeypatch.delenv("SNAPSHOT_INTERVAL_SECONDS", raising=False)
        assert _resolve_interval() == DEFAULT_INTERVAL_SECONDS
