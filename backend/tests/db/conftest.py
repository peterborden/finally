"""Fixtures for the db test suite — each test gets an isolated temp database."""

import pytest


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point the db layer at a fresh temp file via FINALLY_DB_PATH."""
    path = tmp_path / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    return path


@pytest.fixture
def db(db_path):
    """An initialized (schema + seed) empty-default database."""
    from app.db import init_db

    init_db()
    return db_path


@pytest.fixture
def conn(db):
    """An open, committed-on-exit connection against the initialized db."""
    from app.db import connection

    with connection() as c:
        yield c
