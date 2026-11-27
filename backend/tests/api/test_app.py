"""Tests for the create_app() factory wiring (§7)."""

from __future__ import annotations

from app.main import create_app


def test_create_app_boots_without_db_or_chat():
    """App must build even when app.db and app.api.chat are absent (worktree)."""
    app = create_app()
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/api/health" in routes
    assert "/api/portfolio" in routes
    assert "/api/portfolio/trade" in routes
    assert "/api/watchlist" in routes
    assert "/api/stream/prices" in routes


def test_placeholder_root_when_static_absent(client):
    """With no built frontend, '/' returns a placeholder rather than crashing."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "backend running"
