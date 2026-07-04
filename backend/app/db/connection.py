"""Env-driven SQLite connection helper and lazy database initialization."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from .schema import SCHEMA_STATEMENTS
from .seed import seed_defaults

logger = logging.getLogger(__name__)

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


def init_database(db_path: str | Path | None = None) -> None:
    """Lazily create the schema and seed default data.

    Safe to call on every request: table creation uses CREATE TABLE IF NOT
    EXISTS and seeding uses INSERT OR IGNORE, so repeated calls are cheap
    no-ops after the first.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    is_new = not path.exists()

    conn = get_connection(path)
    try:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        seed_defaults(conn)
    finally:
        conn.close()

    if is_new:
        logger.info("Initialized new database at %s", path)
