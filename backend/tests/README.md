# ChimeraFlow Backend Tests

Test suite for MCP connectors and rule engine.

## Structure

```
tests/
├── __init__.py
├── test_connectors.py      # Contract tests (R1-R4)
├── test_properties.py      # Property-Based Tests (P1-P6)
└── test_health.py          # API health check tests
```

## Installation

Install test dependencies:

```bash
pip install -r requirements.txt
```

This includes:
- `pytest` — Test runner
- `pytest-asyncio` — Async test support
- `hypothesis` — Property-based testing framework

## Running Tests

### All tests

```bash
# From backend/ directory
python -m pytest tests/ -v
```

### Specific test file

```bash
python -m pytest tests/test_connectors.py -v
python -m pytest tests/test_properties.py -v
```

### Specific test class or function

```bash
python -m pytest tests/test_connectors.py::TestConnectorContract -v
python -m pytest tests/test_properties.py::TestNormalizationProperties::test_normalization_idempotent -v
```

### With coverage

```bash
python -m pytest tests/ --cov=mcp_servers --cov-report=html
```

## Test Categories

### Contract Tests (`test_connectors.py`)

Validates compliance with `connectors-spec.md`:

- **R1**: All connectors implement `fetch_records()` and `health_check()`
- **R2**: Records conform to unified schema
- **R3**: Health checks are cached for 30 seconds
- **R4**: Parse errors are counted, not crashed

### Property-Based Tests (`test_properties.py`)

Uses Hypothesis to validate properties from `Roadmap.md §7`:

- **P1** Provenance conservation: all emitted data comes from source records
- **P2** Normalization idempotence: `norm(norm(x)) == norm(x)`
- **P3** Parser round-trip: parsing preserves message content
- **P4** Determinism: same inputs → same outputs
- **P6** No fabrication: no invented field values

## Configuration

Test configuration in `pytest.ini`:

```ini
[pytest]
testpaths = tests
asyncio_mode = auto

[hypothesis:dev]
max_examples = 100
deadline = None
```

For CI/CD:

```ini
[hypothesis:ci]
max_examples = 500
deadline = 5000
```

## Test Data

Tests use synthetic data from `data/` directory:

- `data/commandes_clients.txt` — WhatsApp export (50 messages)
- `data/momo_transactions.csv` — Mobile Money CSV (50 transactions)
- `data/tarifs_fournisseurs.xlsx` — Excel price list (to be generated)
- `data/STOCK_ZOBO.mdb` — Access database (to be generated)

Generate missing files:

```bash
# From project root
python scripts/generate_excel.py
python scripts/generate_momo.py
```

## Environment

Tests run in test environment with optional Redis:

```bash
export BACKEND_NODE_ENV=test
python -m pytest tests/
```

Or use `.env.test` file:

```bash
# backend/.env.test
BACKEND_NODE_ENV=test
REDIS_URL=redis://localhost:6379/0  # optional
DATA_DIR=../data
```

## Kiro Hook Integration

When a connector file is saved, the `parser-test` hook automatically runs:

```bash
# Triggered by .kiro/hooks/parser-test.json
python -m pytest tests/test_connectors.py tests/test_properties.py -v --tb=short
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'hypothesis'`

Install dependencies:

```bash
pip install -r requirements.txt
```

### `ValueError: Required environment variable 'REDIS_URL' is not set`

Set test environment:

```bash
export BACKEND_NODE_ENV=test
```

Or add to `.env.test`.

### Test data files not found

Generate synthetic data:

```bash
python scripts/generate_momo.py
python scripts/generate_excel.py  # requires openpyxl
```

---

_Last updated: 2026-11-13_
