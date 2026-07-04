"""SQLite persistence layer for FinAlly.

Public API:
    init_database  - Lazily create the schema and seed default data (idempotent)
    get_db_path    - Resolve the SQLite database path (FINALLY_DB_PATH or default)
    get_connection - Open a Row-factory sqlite3 connection, creating parent dirs
    DEFAULT_TICKERS - The 10 default watchlist tickers
    DEFAULT_CASH   - The default starting cash balance (10000.0)
"""

from .connection import get_connection, get_db_path, init_database
from .seed import DEFAULT_CASH, DEFAULT_TICKERS

__all__ = [
    "init_database",
    "get_db_path",
    "get_connection",
    "DEFAULT_TICKERS",
    "DEFAULT_CASH",
]
