"""TestClient tests for the FastAPI app factory.

Covers health (APP-02), static placeholder serving (APP-03), SSE route
precedence over the static catch-all (APP-01), and lazy DB creation on the
first request (DB-01).
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.db.schema import TABLE_NAMES
from app.main import create_app


class TestApp:
    """Integration tests for create_app()."""

    @pytest.fixture
    def db_path(self, tmp_path, monkeypatch):
        """Point FINALLY_DB_PATH at an isolated tmp_path file for this test."""
        path = tmp_path / "finally.db"
        monkeypatch.setenv("FINALLY_DB_PATH", str(path))
        return path

    @pytest.fixture
    def client(self, db_path):
        """A TestClient with the lifespan run (starts/stops the market source)."""
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client

    def test_health(self, client):
        """GET /api/health returns 200 with a healthy status body."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root_serves_placeholder(self, client):
        """GET / returns 200 and serves the placeholder index.html."""
        response = client.get("/")
        assert response.status_code == 200
        assert "finally-placeholder-marker" in response.text

    def test_sse_route_registered(self, client, monkeypatch):
        """GET /api/stream/prices resolves to the SSE endpoint, not a static 404.

        Starlette's TestClient drives the whole ASGI call to completion before
        handing any response back to the test (it does not support partial
        reads of an in-progress stream), so hitting the real infinite-loop
        generator would hang the test forever. The generator checks
        `request.is_disconnected()` right after its first yield, so patching
        that to report "already disconnected" lets the real endpoint run and
        complete deterministically after one iteration while still proving
        route precedence, status, and content-type.
        """

        async def _already_disconnected(self: Request) -> bool:
            return True

        monkeypatch.setattr(Request, "is_disconnected", _already_disconnected)

        response = client.get("/api/stream/prices")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.startswith("retry:")

    def test_db_created_on_first_request(self, db_path, client):
        """The first request lazily creates the DB, seeded with defaults."""
        assert not db_path.exists()

        response = client.get("/api/health")
        assert response.status_code == 200
        assert db_path.exists()

        conn = sqlite3.connect(db_path)
        try:
            table_names = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            assert table_names == set(TABLE_NAMES)

            profile = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = 'default'"
            ).fetchone()
            assert profile is not None
            assert profile[0] == 10000.0

            tickers = {
                row[0]
                for row in conn.execute(
                    "SELECT ticker FROM watchlist WHERE user_id = 'default'"
                )
            }
            assert len(tickers) == 10
        finally:
            conn.close()
