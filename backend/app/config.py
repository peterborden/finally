"""Application configuration.

Loads environment variables from the project-root ``.env`` (via python-dotenv)
and exposes a typed ``Settings`` singleton. Other modules (DB layer, DevOps,
LLM layer) read setting *names* from here so there is a single source of truth.

Symbols other layers consume:
    get_settings() -> Settings          # cached singleton accessor
    settings                            # module-level Settings instance
    Settings.db_path: Path              # resolved SQLite file path (DB layer reads this)
    Settings.llm_mock: bool
    Settings.openrouter_api_key: str
    Settings.massive_api_key: str
    Settings.default_tickers: list[str]
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Project root = .../finally/  (this file is .../finally/backend/app/config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from the project root exactly once at import time. This populates
# os.environ so that both this module and the market-data factory (which reads
# os.environ["MASSIVE_API_KEY"] directly) see the same values.
load_dotenv(PROJECT_ROOT / ".env")

# Default watchlist tickers (PLAN §7 seed data). Kept here so the app can start
# the market-data source before the DB is queried.
DEFAULT_TICKERS: list[str] = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_db_path() -> Path:
    """Resolve the SQLite DB path.

    Defaults to ``<project_root>/db/finally.db``; overridable via the
    ``FINALLY_DB_PATH`` environment variable (DevOps mounts ``/app/db`` in the
    container). Relative overrides are resolved against the project root.
    """
    override = os.environ.get("FINALLY_DB_PATH", "").strip()
    if override:
        p = Path(override).expanduser()
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
    return (PROJECT_ROOT / "db" / "finally.db").resolve()


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of runtime configuration."""

    project_root: Path
    db_path: Path
    llm_mock: bool
    openrouter_api_key: str
    massive_api_key: str
    default_tickers: list[str] = field(default_factory=lambda: list(DEFAULT_TICKERS))

    @property
    def use_massive(self) -> bool:
        """True when a real Massive API key is configured."""
        return bool(self.massive_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton, built from the environment."""
    return Settings(
        project_root=PROJECT_ROOT,
        db_path=_resolve_db_path(),
        llm_mock=_env_bool("LLM_MOCK", False),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
        massive_api_key=os.environ.get("MASSIVE_API_KEY", "").strip(),
    )


# Module-level convenience singletons.
settings = get_settings()
DB_PATH = settings.db_path
