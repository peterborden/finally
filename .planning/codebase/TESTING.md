# Testing Patterns

**Analysis Date:** 2026-07-04

## Test Framework

**Runner:**
- pytest 8.3.0+ with asyncio support
- Config: `backend/pyproject.toml` [tool.pytest.ini_options]

**Key Settings:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

**Assertion Library:**
- Built-in pytest assertions (no explicit library needed)

**Coverage Tool:**
- pytest-cov 5.0.0+
- Config: `[tool.coverage.run]` and `[tool.coverage.report]` in pyproject.toml

**Run Commands:**
```bash
uv run --extra dev pytest -v              # All tests with verbose output
uv run --extra dev pytest --cov=app       # With coverage measurement
uv run --extra dev pytest -v tests/market/test_cache.py  # Single file
uv run --extra dev pytest -k test_update  # Tests matching pattern
```

## Test File Organization

**Location:**
- `backend/tests/` directory
- Parallel structure to source code: `backend/tests/market/` mirrors `backend/app/market/`

**Naming:**
- Files: `test_*.py` (e.g., `test_models.py`, `test_simulator_source.py`)
- Classes: `Test*` (e.g., `TestPriceUpdate`, `TestPriceCache`, `TestGBMSimulator`)
- Methods: `test_*` (e.g., `test_price_update_creation`, `test_direction_up`)

**Directory Structure:**
```
backend/
├── app/
│   ├── market/
│   │   ├── models.py
│   │   ├── cache.py
│   │   └── simulator.py
│   └── __init__.py
├── tests/
│   ├── market/
│   │   ├── test_models.py        # Tests for app/market/models.py
│   │   ├── test_cache.py         # Tests for app/market/cache.py
│   │   ├── test_simulator.py     # Tests for app/market/simulator.py
│   │   └── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   └── __init__.py
└── pyproject.toml
```

## Test Structure

**Suite Organization:**
- One test class per tested module/class
- Multiple test methods per behavior area

Example structure from `backend/tests/market/test_models.py`:
```python
"""Tests for PriceUpdate dataclass."""

import pytest
from app.market.models import PriceUpdate

class TestPriceUpdate:
    """Unit tests for the PriceUpdate model."""

    def test_price_update_creation(self):
        """Test basic PriceUpdate creation."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1234567890.0)
        assert update.ticker == "AAPL"

    def test_change_calculation(self):
        """Test price change calculation."""
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00)
        assert update.change == 0.50
```

**Test Method Pattern:**
1. **Docstring:** Brief description of what's being tested
2. **Setup:** Create objects and state
3. **Action:** Call the method/function under test
4. **Assert:** Verify results

```python
def test_direction_up(self):
    """Test direction calculation (up)."""
    # Setup
    update = PriceUpdate(ticker="AAPL", price=191.00, previous_price=190.00, ...)
    
    # Action (implicit in setup)
    # The direction property is computed in the constructor
    
    # Assert
    assert update.direction == "up"
```

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Creating Mock Objects:**
```python
from unittest.mock import MagicMock, patch

# Create a mock object
mock_snap = MagicMock()
mock_snap.ticker = "AAPL"
mock_snap.last_trade = MagicMock()
mock_snap.last_trade.price = 190.50
```

**Patching Functions/Methods:**
```python
# Patch environment variable
with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
    source = create_market_data_source(cache)
    assert isinstance(source, MassiveDataSource)

# Patch method on object
with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
    await source._poll_once()

# Patch with side effects (exceptions)
with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
    await source._poll_once()  # Should not raise
```

**Helper Functions for Test Data:**
```python
def _make_snapshot(ticker: str, price: float, timestamp_ms: int) -> MagicMock:
    """Create a mock Massive snapshot object."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = MagicMock()
    snap.last_trade.price = price
    snap.last_trade.timestamp = timestamp_ms
    return snap
```

**What to Mock:**
- External APIs (HTTP calls via `patch.object`)
- Environment variables (via `patch.dict(os.environ)`)
- System time (if testing timing logic)
- Random generators (if testing probabilistic behavior)

**What NOT to Mock:**
- Core business logic (test real behavior)
- Your own classes (test real instances)
- Pure functions (no side effects, test directly)
- Example: Test `GBMSimulator` with real price calculations, don't mock `step()`

## Fixtures and Factories

**Test Data:**
Typically created inline or via helper functions. Example from `test_factory.py`:

```python
def test_creates_simulator_when_no_api_key(self):
    """Test that simulator is created when MASSIVE_API_KEY is not set."""
    cache = PriceCache()  # Inline fixture creation

    with patch.dict(os.environ, {}, clear=True):
        source = create_market_data_source(cache)

    assert isinstance(source, SimulatorDataSource)
```

**Shared Fixtures (in `conftest.py`):**
```python
"""Pytest configuration and fixtures."""

import pytest

@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
```

**Location:**
- Global fixtures: `backend/tests/conftest.py`
- Module-specific fixtures: Within test file or subfolder conftest.py

## Coverage

**Requirements:** No hard enforcement configured

**Target:** Aim for high coverage on business logic (`app/market/` especially)

**View Coverage:**
```bash
uv run --extra dev pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

**Coverage Configuration (pyproject.toml):**
```toml
[tool.coverage.run]
source = ["app"]
omit = ["tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## Test Types

**Unit Tests:**
- Test single class/function in isolation
- Fast, no I/O or external dependencies
- Location: `backend/tests/market/test_models.py`, `test_cache.py`
- Example: Testing `PriceUpdate.change_percent` calculation, `PriceCache.update()`

**Integration Tests:**
- Test multiple components working together
- May use real async operations (asyncio.sleep, background tasks)
- Example from `test_simulator_source.py`:

```python
@pytest.mark.asyncio
class TestSimulatorDataSource:
    """Integration tests for the SimulatorDataSource."""

    async def test_start_populates_cache(self):
        """Test that start() immediately populates the cache."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL", "GOOGL"])

        # Cache should have seed prices immediately
        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None

        await source.stop()
```

**E2E Tests:**
- Not yet implemented in backend
- Planned for `test/` directory with Playwright
- Will test full app flow: UI → API → database → responses

## Common Patterns

### Async Testing

**Marking async tests:**
```python
@pytest.mark.asyncio
class TestSimulatorDataSource:
    async def test_prices_update_over_time(self):
        """Test that prices are updated periodically."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])

        initial_version = cache.version
        await asyncio.sleep(0.3)  # Several update cycles

        assert cache.version > initial_version
        await source.stop()
```

**Proper cleanup:**
```python
# Always await stop() to clean up background tasks
async def test_something(self):
    source = SimulatorDataSource(...)
    await source.start([...])
    
    # do stuff
    
    await source.stop()  # Critical for teardown
```

### Error Testing

**Testing exception handling:**
```python
def test_immutability(self):
    """Test that PriceUpdate is immutable."""
    update = PriceUpdate(ticker="AAPL", price=190.50, ...)

    with pytest.raises(AttributeError):
        update.price = 200.00  # Should raise error
```

**Testing graceful error recovery:**
```python
async def test_api_error_does_not_crash(self):
    """Test that API errors don't crash the poller."""
    cache = PriceCache()
    source = MassiveDataSource(api_key="test-key", price_cache=cache)
    source._tickers = ["AAPL"]
    source._client = MagicMock()

    with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
        await source._poll_once()  # Should not raise

    assert cache.get_price("AAPL") is None  # No update happened
```

### Edge Cases

**Testing boundary conditions:**
```python
def test_change_percent_zero_previous(self):
    """Test percentage change with zero previous price."""
    update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=0.00)
    assert update.change_percent == 0.0  # Guard against division by zero

def test_empty_step(self):
    """Test stepping with no tickers."""
    sim = GBMSimulator(tickers=[])
    result = sim.step()
    assert result == {}  # Empty result, not None or error
```

**Testing idempotency:**
```python
async def test_stop_is_idempotent(self):
    """Test that stop() can be called multiple times."""
    source = MassiveDataSource(api_key="test-key", ...)
    await source.stop()
    await source.stop()  # Should not raise
```

**Testing no-op operations:**
```python
def test_add_duplicate_is_noop(self):
    """Test that adding a duplicate ticker is a no-op."""
    sim = GBMSimulator(tickers=["AAPL"])
    sim.add_ticker("AAPL")
    assert len(sim._tickers) == 1  # Still just 1, not 2

def test_remove_nonexistent_is_noop(self):
    """Test that removing a non-existent ticker is a no-op."""
    sim = GBMSimulator(tickers=["AAPL"])
    sim.remove_ticker("NOPE")  # Should not raise
```

### Mathematical/Algorithmic Testing

**Testing algorithm properties (not exact values):**
```python
def test_prices_are_positive(self):
    """GBM prices can never go negative (exp() is always positive)."""
    sim = GBMSimulator(tickers=["AAPL"])
    for _ in range(10_000):
        prices = sim.step()
        assert prices["AAPL"] > 0  # Property test

def test_prices_change_over_time(self):
    """After many steps, prices should have drifted from their seeds."""
    sim = GBMSimulator(tickers=["AAPL"])
    initial_price = sim.get_price("AAPL")

    for _ in range(1000):
        sim.step()

    final_price = sim.get_price("AAPL")
    assert final_price != initial_price  # Drifted, not exact
```

**Testing correlation logic:**
```python
def test_pairwise_correlation_tech_stocks(self):
    """Test that tech stocks have high correlation."""
    corr = GBMSimulator._pairwise_correlation("AAPL", "GOOGL")
    assert corr == 0.6  # Known value for tech sector

def test_cholesky_rebuilds_on_add(self):
    """Test that Cholesky matrix is rebuilt when tickers are added."""
    sim = GBMSimulator(tickers=["AAPL"])
    assert sim._cholesky is None  # Only 1 ticker, no correlation matrix
    sim.add_ticker("GOOGL")
    assert sim._cholesky is not None  # Now 2 tickers, matrix exists
```

## Test Execution

**Running all tests:**
```bash
cd backend
uv run --extra dev pytest -v
```

**Running specific test file:**
```bash
uv run --extra dev pytest -v tests/market/test_models.py
```

**Running specific test class:**
```bash
uv run --extra dev pytest -v tests/market/test_models.py::TestPriceUpdate
```

**Running specific test method:**
```bash
uv run --extra dev pytest -v tests/market/test_models.py::TestPriceUpdate::test_change_calculation
```

**Running by pattern:**
```bash
uv run --extra dev pytest -k "test_direction"  # All tests with "direction" in name
```

**With coverage:**
```bash
uv run --extra dev pytest --cov=app --cov-report=term-missing
```

---

*Testing analysis: 2026-07-04*
