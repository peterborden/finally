"""Tests for the repository functions (BUILD_CONTRACT §3)."""

import pytest

from app.db import (
    add_message,
    add_watchlist_ticker,
    delete_position,
    get_position,
    get_positions,
    get_profile,
    get_recent_messages,
    get_snapshots,
    get_trades,
    get_watchlist,
    record_snapshot,
    record_trade,
    remove_watchlist_ticker,
    set_cash_balance,
    upsert_position,
)


# --------------------------------------------------------------------------- #
# profile
# --------------------------------------------------------------------------- #
def test_set_and_get_cash_balance(conn):
    set_cash_balance(conn, 8075.5)
    assert get_profile(conn)["cash_balance"] == 8075.5


# --------------------------------------------------------------------------- #
# watchlist
# --------------------------------------------------------------------------- #
def test_add_watchlist_normalizes_and_returns_row(conn):
    row = add_watchlist_ticker(conn, "  pypl ")
    assert row["ticker"] == "PYPL"
    assert row["id"]
    assert row["added_at"]
    assert set(row.keys()) == {"id", "ticker", "added_at"}


def test_add_watchlist_is_idempotent(conn):
    first = add_watchlist_ticker(conn, "PYPL")
    second = add_watchlist_ticker(conn, "pypl")
    assert first["id"] == second["id"]
    tickers = [w["ticker"] for w in get_watchlist(conn)]
    assert tickers.count("PYPL") == 1


def test_remove_watchlist_returns_bool(conn):
    add_watchlist_ticker(conn, "PYPL")
    assert remove_watchlist_ticker(conn, "pypl") is True
    assert remove_watchlist_ticker(conn, "PYPL") is False


def test_watchlist_insertion_order_preserved(conn):
    # Clear seeded rows then add in a known order.
    for w in list(get_watchlist(conn)):
        remove_watchlist_ticker(conn, w["ticker"])
    for t in ("ZZZ", "AAA", "MMM"):
        add_watchlist_ticker(conn, t)
    assert [w["ticker"] for w in get_watchlist(conn)] == ["ZZZ", "AAA", "MMM"]


# --------------------------------------------------------------------------- #
# positions
# --------------------------------------------------------------------------- #
def test_upsert_insert_then_get(conn):
    pos = upsert_position(conn, "aapl", 10, 190.0)
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 190.0
    fetched = get_position(conn, "AAPL")
    assert fetched["id"] == pos["id"]


def test_upsert_updates_and_preserves_id(conn):
    first = upsert_position(conn, "AAPL", 10, 190.0)
    second = upsert_position(conn, "AAPL", 15, 191.0)
    assert first["id"] == second["id"]
    assert second["quantity"] == 15
    assert second["avg_cost"] == 191.0
    assert len(get_positions(conn)) == 1


def test_weighted_avg_cost_roundtrip(conn):
    # Buy 10 @ 190, then buy 10 @ 210 → weighted avg 200 (computed by caller).
    upsert_position(conn, "AAPL", 10, 190.0)
    prev = get_position(conn, "AAPL")
    new_qty = prev["quantity"] + 10
    new_avg = (prev["quantity"] * prev["avg_cost"] + 10 * 210.0) / new_qty
    upsert_position(conn, "AAPL", new_qty, new_avg)
    result = get_position(conn, "AAPL")
    assert result["quantity"] == 20
    assert result["avg_cost"] == pytest.approx(200.0)


def test_delete_position(conn):
    upsert_position(conn, "AAPL", 10, 190.0)
    delete_position(conn, "aapl")
    assert get_position(conn, "AAPL") is None
    # deleting an absent position is a no-op
    delete_position(conn, "AAPL")


def test_get_position_missing_returns_none(conn):
    assert get_position(conn, "NOPE") is None


# --------------------------------------------------------------------------- #
# trades
# --------------------------------------------------------------------------- #
def test_record_trade_shape_and_normalization(conn):
    trade = record_trade(conn, "aapl", "BUY", 5, 192.5)
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 5
    assert trade["price"] == 192.5
    assert set(trade.keys()) == {"id", "ticker", "side", "quantity", "price", "executed_at"}


def test_get_trades_newest_first_and_limit(conn):
    record_trade(conn, "AAPL", "buy", 1, 100.0)
    record_trade(conn, "GOOGL", "buy", 2, 200.0)
    record_trade(conn, "MSFT", "sell", 3, 300.0)
    all_trades = get_trades(conn)
    assert [t["ticker"] for t in all_trades] == ["MSFT", "GOOGL", "AAPL"]
    limited = get_trades(conn, limit=2)
    assert len(limited) == 2
    assert limited[0]["ticker"] == "MSFT"


# --------------------------------------------------------------------------- #
# snapshots
# --------------------------------------------------------------------------- #
def test_record_snapshot_shape(conn):
    snap = record_snapshot(conn, 11925.0)
    assert snap["total_value"] == 11925.0
    assert set(snap.keys()) == {"id", "total_value", "recorded_at"}


def test_snapshots_oldest_to_newest(conn):
    record_snapshot(conn, 100.0)
    record_snapshot(conn, 200.0)
    record_snapshot(conn, 300.0)
    snaps = get_snapshots(conn)
    assert [s["total_value"] for s in snaps] == [100.0, 200.0, 300.0]


def test_snapshots_limit_returns_latest_oldest_first(conn):
    for v in (100.0, 200.0, 300.0, 400.0):
        record_snapshot(conn, v)
    snaps = get_snapshots(conn, limit=2)
    assert [s["total_value"] for s in snaps] == [300.0, 400.0]


# --------------------------------------------------------------------------- #
# chat messages
# --------------------------------------------------------------------------- #
def test_add_message_user_no_actions(conn):
    msg = add_message(conn, "user", "buy 5 apple")
    assert msg["role"] == "user"
    assert msg["content"] == "buy 5 apple"
    assert msg["actions"] is None
    assert set(msg.keys()) == {"id", "role", "content", "actions", "created_at"}


def test_add_message_actions_json_roundtrip(conn):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}], "errors": []}
    msg = add_message(conn, "assistant", "Bought 5 AAPL.", actions=actions)
    assert msg["actions"] == actions
    recent = get_recent_messages(conn)
    assert recent[-1]["actions"] == actions
    assert isinstance(recent[-1]["actions"], dict)


def test_get_recent_messages_ordering_and_limit(conn):
    for i in range(5):
        add_message(conn, "user", f"m{i}")
    recent = get_recent_messages(conn, limit=3)
    assert [m["content"] for m in recent] == ["m2", "m3", "m4"]


def test_get_recent_messages_default_limit(conn):
    for i in range(25):
        add_message(conn, "user", f"m{i}")
    recent = get_recent_messages(conn)
    assert len(recent) == 20
    assert recent[0]["content"] == "m5"
    assert recent[-1]["content"] == "m24"
