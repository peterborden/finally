"""Database connection management and path resolution.

The DB path defaults to ``db/finally.db`` relative to the project root and is
overridable via the ``FINALLY_DB_PATH`` environment variable (DevOps mounts
``/app/db`` in the container). Path resolution lives here so the db package has
no upstream dependency on the Backend-owned ``config.py``.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# connection.py lives at <root>/backend/app/db/connection.py — the project root
# is four parents up (db -> app -> backend -> root).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "finally.db"


def get_db_path() -> Path:
    """Resolve the SQLite file path.

    Honors ``FINALLY_DB_PATH`` if set (and non-empty); otherwise defaults to
    ``<project_root>/db/finally.db``.
    """
    override = os.environ.get("FINALLY_DB_PATH")
    if override and override.strip():
        return Path(override).expanduser()
    return _DEFAULT_DB_PATH


def _connect(path: Path) -> sqlite3.Connection:
    """Open a connection with the pragmas every caller expects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection.

    - ``row_factory`` is ``sqlite3.Row`` (dict-like row access).
    - ``foreign_keys`` are ON and WAL journaling is enabled.
    - Commits on clean exit; rolls back and re-raises on exception.
    """
    conn = _connect(get_db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
