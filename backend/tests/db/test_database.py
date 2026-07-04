"""Tests for the SQLite schema, seed data, and init_database idempotency."""

import sqlite3

import pytest

from app.db import DEFAULT_CASH, DEFAULT_TICKERS, init_database
from app.db.schema import TABLE_NAMES


class TestDatabase:
    """Unit tests for schema creation, default seeding, and idempotent init."""

    @pytest.fixture
    def db_path(self, tmp_path):
        """An isolated database path under pytest's tmp_path."""
        return tmp_path / "sub" / "finally.db"

    def test_init_creates_file(self, db_path):
        """init_database creates the database file (and parent dirs)."""
        assert not db_path.exists()
        init_database(db_path)
        assert db_path.exists()

    def test_all_six_tables_present(self, db_path):
        """init_database creates exactly the six expected tables."""
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = {row[0] for row in rows}
        finally:
            conn.close()
        assert table_names == set(TABLE_NAMES)
        assert table_names == {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }

    def test_expected_columns(self, db_path):
        """Each table has the expected columns; user_id present on all six."""
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        try:
            for table in TABLE_NAMES:
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if table == "users_profile":
                    assert "id" in columns
                    assert "cash_balance" in columns
                    assert "created_at" in columns
                else:
                    assert "user_id" in columns, f"{table} missing user_id"

            watchlist_columns = {row[1] for row in conn.execute("PRAGMA table_info(watchlist)")}
            assert watchlist_columns == {"id", "user_id", "ticker", "added_at"}

            positions_columns = {row[1] for row in conn.execute("PRAGMA table_info(positions)")}
            assert positions_columns == {
                "id",
                "user_id",
                "ticker",
                "quantity",
                "avg_cost",
                "updated_at",
            }
        finally:
            conn.close()

        # UNIQUE(user_id, ticker) enforced on watchlist and positions.
        # Use a ticker outside the default seed set to isolate this check.
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                ("dup-1", "default", "ZZZZ", "now"),
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    ("dup-2", "default", "ZZZZ", "now"),
                )
            conn.rollback()

            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("pos-1", "default", "ZZZZ", 1.0, 190.0, "now"),
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("pos-2", "default", "ZZZZ", 2.0, 200.0, "now"),
                )
            conn.rollback()
        finally:
            conn.close()

    def test_seed_profile_and_watchlist(self, db_path):
        """Seeding creates one $10k profile and the 10 expected tickers."""
        init_database(db_path)
        conn = sqlite3.connect(db_path)
        try:
            profile = conn.execute(
                "SELECT id, cash_balance FROM users_profile WHERE id = 'default'"
            ).fetchone()
            assert profile is not None
            assert profile[1] == DEFAULT_CASH == 10000.0

            tickers = {
                row[0] for row in conn.execute("SELECT ticker FROM watchlist WHERE user_id = ?",
                                                ("default",))
            }
            assert tickers == set(DEFAULT_TICKERS)
            assert len(DEFAULT_TICKERS) == 10
        finally:
            conn.close()

    def test_idempotent_reinit(self, db_path):
        """Calling init_database twice keeps counts stable and raises nothing."""
        init_database(db_path)
        init_database(db_path)

        conn = sqlite3.connect(db_path)
        try:
            profile_count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
            watchlist_count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        finally:
            conn.close()

        assert profile_count == 1
        assert watchlist_count == 10
