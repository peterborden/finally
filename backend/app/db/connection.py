"""Env-driven SQLite connection helper."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("db/finally.db")


def get_db_path() -> Path:
    """Resolve the SQLite database path from FINALLY_DB_PATH, else the default.

    Default: db/finally.db (relative to the process working directory).
    """
    env_path = os.environ.get("FINALLY_DB_PATH")
    return Path(env_path) if env_path else DEFAULT_DB_PATH


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection, creating the parent directory if missing.

    Returns a connection with row_factory set to sqlite3.Row so query results
    can be accessed by column name.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
