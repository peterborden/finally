"""Tests for path resolution and the connection() context manager."""

import sqlite3

import pytest


def test_default_db_path_is_project_root_db_file(monkeypatch):
    monkeypatch.delenv("FINALLY_DB_PATH", raising=False)
    from app.db.connection import get_db_path

    path = get_db_path()
    assert path.name == "finally.db"
    assert path.parent.name == "db"


def test_env_override_wins(monkeypatch, tmp_path):
    target = tmp_path / "custom" / "mydb.sqlite"
    monkeypatch.setenv("FINALLY_DB_PATH", str(target))
    from app.db.connection import get_db_path

    assert get_db_path() == target


def test_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", "   ")
    from app.db.connection import get_db_path

    assert get_db_path().name == "finally.db"


def test_connection_has_row_factory_and_foreign_keys(db_path):
    from app.db import connection

    with connection() as conn:
        assert conn.row_factory is sqlite3.Row
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal.lower() == "wal"


def test_connection_commits_on_clean_exit(db):
    from app.db import connection

    with connection() as conn:
        conn.execute("UPDATE users_profile SET cash_balance = 4242.0 WHERE id = 'default'")

    with connection() as conn:
        val = conn.execute("SELECT cash_balance FROM users_profile WHERE id='default'").fetchone()[0]
    assert val == 4242.0


def test_connection_rolls_back_on_exception(db):
    from app.db import connection

    with pytest.raises(RuntimeError):
        with connection() as conn:
            conn.execute("UPDATE users_profile SET cash_balance = 999.0 WHERE id='default'")
            raise RuntimeError("boom")

    with connection() as conn:
        val = conn.execute("SELECT cash_balance FROM users_profile WHERE id='default'").fetchone()[0]
    assert val == 10000.0
