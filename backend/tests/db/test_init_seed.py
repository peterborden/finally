"""Tests for init_db idempotency and seed correctness."""

from app.db import connection, get_profile, get_watchlist, init_db
from app.db.repositories import DEFAULT_TICKERS


def test_creates_all_six_tables(db):
    with connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r["name"] for r in rows}
    for expected in (
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    ):
        assert expected in names


def test_seeds_default_profile(db):
    with connection() as conn:
        profile = get_profile(conn)
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"]


def test_seeds_ten_default_tickers_in_order(db):
    with connection() as conn:
        wl = get_watchlist(conn)
    assert [w["ticker"] for w in wl] == list(DEFAULT_TICKERS)
    assert len(wl) == 10


def test_init_is_idempotent(db):
    # Re-running init must not duplicate seed rows.
    init_db()
    init_db()
    with connection() as conn:
        profiles = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
        tickers = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    assert profiles == 1
    assert tickers == 10


def test_init_does_not_clobber_existing_data(db):
    from app.db import set_cash_balance

    with connection() as conn:
        set_cash_balance(conn, 555.0)
    # A second init must preserve user mutations (tables non-empty → no reseed).
    init_db()
    with connection() as conn:
        assert get_profile(conn)["cash_balance"] == 555.0
