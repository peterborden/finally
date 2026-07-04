# Coding Conventions

**Analysis Date:** 2026-07-04

## Naming Patterns

**Files:**
- snake_case throughout
- Example: `simulator.py`, `price_cache.py`, `massive_client.py`
- Test files: `test_*.py` (e.g., `test_models.py`, `test_simulator_source.py`)

**Classes:**
- PascalCase (CapWords)
- Example: `GBMSimulator`, `PriceCache`, `MarketDataSource`, `MassiveDataSource`
- Abstract base classes: `MarketDataSource` (inherits from ABC)

**Functions and Methods:**
- snake_case
- Public: `get_price()`, `add_ticker()`, `update()`, `create_market_data_source()`
- Private (prefixed with `_`): `_add_ticker_internal()`, `_rebuild_cholesky()`, `_poll_once()`, `_generate_events()`
- Static methods: decorated with `@staticmethod` (e.g., `_pairwise_correlation()`)

**Variables:**
- snake_case
- Private instance attributes: `_prices`, `_cache`, `_task`, `_api_key`, `_tickers`
- Protected by convention (not Python-enforced)

**Constants:**
- UPPER_SNAKE_CASE
- Example: `DEFAULT_DT`, `TRADING_SECONDS_PER_YEAR`, `SEED_PRICES`, `CORRELATION_GROUPS`
- Defined in module-level constants file: `app/market/seed_prices.py`

## Code Style

**Formatter/Linter:**
- **Ruff** for linting and style checking
- Configuration: `pyproject.toml` [tool.ruff]
- Line length: 100 characters (E501 ignored)
- Python target: 3.12+

**Ruff Rules:**
```
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # Line too long (handled by formatter)
```

- E: pycodestyle errors
- F: Pyflakes (undefined names, unused imports)
- I: isort (import ordering)
- N: pep8-naming (naming conventions)
- W: pycodestyle warnings

**Type System:**
- Python 3.10+ union syntax: `str | None` instead of `Optional[str]`
- Full type hints on function signatures
- Return type hints always specified
- Use `from __future__ import annotations` for forward references

Example:
```python
from __future__ import annotations

def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create the appropriate market data source..."""
```

**Classes and Data:**
- Frozen dataclasses for immutable data
- Use `slots=True` for memory efficiency
- Example from `app/market/models.py`:
```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)
```

## Import Organization

**Order of imports:**
1. `from __future__ import annotations` (PEP 563)
2. Standard library imports (abc, asyncio, logging, os, etc.)
3. Third-party imports (fastapi, numpy, massive, etc.)
4. Relative local imports (from .models import, from .cache import)

**Example from `backend/app/market/simulator.py`:**
```python
from __future__ import annotations

import asyncio
import logging
import math
import random

import numpy as np

from .cache import PriceCache
from .interface import MarketDataSource
from .seed_prices import (
    CORRELATION_GROUPS,
    SEED_PRICES,
    TICKER_PARAMS,
)

logger = logging.getLogger(__name__)
```

**Module Imports:**
- Use relative imports within packages: `from .cache import PriceCache`
- Module logger: `logger = logging.getLogger(__name__)` at module level
- Explicit `__all__` in `__init__.py` files with docstring

Example from `app/market/__init__.py`:
```python
"""Market data subsystem for FinAlly.

Public API:
    PriceUpdate         - Immutable price snapshot dataclass
    PriceCache          - Thread-safe in-memory price store
    ...
"""

from .cache import PriceCache
from .models import PriceUpdate

__all__ = [
    "PriceUpdate",
    "PriceCache",
    ...
]
```

## Error Handling

**Strategy:** Specific errors first, general catch-all last

**Pattern:**
```python
try:
    # Normal operation
    price = snap.last_trade.price
except (AttributeError, TypeError) as e:
    logger.warning("Skipping snapshot for %s: %s", ticker, e)
except Exception as e:
    logger.error("Operation failed: %s", e)
    # Usually don't re-raise; let system continue gracefully
```

**When to catch vs. let fail:**
- Network errors in polling loops: catch, log warning, continue
- Missing attributes in parsed data: catch, log warning, skip record
- Configuration errors at startup: let fail (fatal)
- API key invalid: catch, log error, disable feature

**Logging levels:**
- `logger.debug()`: Algorithm details, state changes (e.g., random events)
- `logger.info()`: Lifecycle events (component start/stop), important state
- `logger.warning()`: Recoverable errors (missing data, skipped items)
- `logger.error()`: Serious issues (API failures, unexpected exceptions)

## Logging

**Framework:** Python's built-in `logging`

**Pattern:**
```python
import logging

logger = logging.getLogger(__name__)

class MyClass:
    async def start(self):
        logger.info("Component started: %d items", count)
    
    async def _poll_once(self):
        try:
            # work...
        except ValueError as e:
            logger.warning("Bad data: %s", e)
```

**When to log:**
- Component lifecycle: `logger.info("Started", extra_context)`
- Recoverable errors: `logger.warning()`
- Fatal errors: `logger.error()`
- Algorithm details (correlated moves, random events): `logger.debug()`

**Don't log:**
- API keys, secrets (never include in error messages)
- Excessive data (don't dump full dicts/lists)

## Comments

**When to comment:**
- Algorithm explanation (math formulas, correlation logic)
- Non-obvious design decisions
- Workarounds or known limitations
- Example from `app/market/simulator.py`:

```python
# 500ms expressed as a fraction of a trading year
# 252 trading days * 6.5 hours/day * 3600 seconds/hour = 5,896,800 seconds
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600
```

**Docstrings:**
- Module docstring at the top of every file
- Class docstring explaining purpose and usage
- Method/function docstring with brief description
- Include lifecycle details for complex components

Example from `app/market/interface.py`:
```python
"""Abstract interface for market data sources."""

class MarketDataSource(ABC):
    """Contract for market data providers.
    
    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL"])
        await source.add_ticker("TSLA")
        await source.stop()
    """
```

**ASCII art in docstrings:**
- Use for complex data flows or algorithms
- Example from `app/market/simulator.py`:
```python
"""Geometric Brownian Motion simulator for correlated stock prices.

Math:
    S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
...
"""
```

## Function Design

**Size guideline:** Keep functions focused and testable (typically <50 lines)

**Parameters:**
- Type-annotated
- Use default values for optional parameters
- Avoid global state / use dependency injection

Example:
```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Dependency injection: price_cache passed explicitly."""
```

**Return values:**
- Always type-annotated
- Return early with guard clauses to reduce nesting
- Return `None` explicitly for "no result" cases

Example of guard clause:
```python
def add_ticker(self, ticker: str) -> None:
    if ticker in self._prices:
        return  # Early return, no-op if already exists
    self._tickers.append(ticker)
```

**Async functions:**
- Prefix task names for clarity: `asyncio.create_task(self._poll_loop(), name="massive-poller")`
- Use `asyncio.to_thread()` to run sync code without blocking: `snapshots = await asyncio.to_thread(self._fetch_snapshots)`
- Proper cleanup: `try/finally` with `task.cancel()` and `await task`

## Module Design

**Exports:**
- Always define `__all__` in `__init__.py`
- Include docstring listing public API (types, functions)
- Example from `app/market/__init__.py`:

```python
__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

**Factory Pattern:**
- Use `create_*` functions for dependency injection
- Avoids global state and singletons
- Example: `create_market_data_source()`, `create_stream_router()`

**Interfaces:**
- Abstract base classes for pluggable implementations
- Example: `MarketDataSource` (abstract) → `SimulatorDataSource`, `MassiveDataSource` (concrete)

**Thread Safety:**
- Document shared mutable state
- Use `threading.Lock()` for critical sections
- Example from `app/market/cache.py`:

```python
"""Thread-safe in-memory cache.

Writers: SimulatorDataSource or MassiveDataSource (one at a time).
Readers: SSE streaming endpoint, portfolio valuation, trade execution.
"""

def update(self, ticker: str, price: float, ...) -> PriceUpdate:
    with self._lock:
        # Protected update
```

---

*Convention analysis: 2026-07-04*
