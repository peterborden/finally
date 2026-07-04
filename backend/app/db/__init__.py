"""SQLite persistence layer for FinAlly.

Public API:
    get_db_path  - Resolve the SQLite database path (FINALLY_DB_PATH or default)
    get_connection - Open a Row-factory sqlite3 connection, creating parent dirs
"""

from .connection import get_connection, get_db_path

__all__ = [
    "get_db_path",
    "get_connection",
]
