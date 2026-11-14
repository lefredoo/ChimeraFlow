# ChimeraFlow Backend Tests

Test suite for MCP connectors and rule engine.

## Structure

```
tests/
├── __init__.py
├── conftest.py                 # Test environment variables, Hypothesis profiles, api_client fixture
├── factories.py                # In-memory unified records (WhatsApp, Access, Excel)
├── test_api_correlations.py    # Seeding, execution, foreign keys, idempotence, cascade
├── test_connectors.py          # Contract tests (R1-R4)
├── test_access_readers.py      # ACCESS_READER selection, mdbtools vs access-parser equivalence
├── test_migrations.py          # alembic upgrade head / downgrade base, no drift with the models
├── test_connector_payloads.py  # Source field names, product entities, parse errors
├── test_properties.py          # Property-Based Tests (P1-P6)
├── test_normalizer.py          # Normalization variants + idempotence (P2)
├── test_interpreter.py         # Rule execution, provenance, where conditions
├── test_schemas.py             # Rule schema validation
└── test_health.py              # API health check tests
```

## Installation

Install test dependencies in the Python 3.13 virtual environment (`backend/.venv`):

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt   # Windows: .venv\Scripts\python.exe
```

This includes:
- `pytest` — Test runner
- `pytest-asyncio` — Async test support
- `hypothesis` — Property-based testing framework

## Running Tests

### All tests

```bash
# From backend/ directory (Windows: .venv\Scripts\python.exe)
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m ruff check .     # lint (pyflakes rules)
```

Locally on Windows there is no mdbtools: the mdbtools tests are skipped
(3 skipped). Run the full suite in Docker to execute them.

### All tests in Docker (with mdbtools, nothing skipped)

From the repository root (one line, PowerShell):

```powershell
docker build --target test -t chimeraflow-backend-test backend; docker run --rm -v "${PWD}/data:/data:ro" chimeraflow-backend-test
```

Bash: replace `;` with `&&` and `${PWD}` with `$PWD`. Add
`python -m pytest tests -q --hypothesis-profile=ci` after the image name to run
the CI profile. The `test` stage of `backend/Dockerfile` installs
`requirements-dev.txt` on top of the runtime image, which provides `mdb-export`.

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
python -m pytest tests/ --cov=mcp_servers --cov=engine --cov-report=html
```

## Test Categories

### Contract Tests (`test_connectors.py`)

Validates compliance with `connectors-spec.md`:

- **R1**: All connectors implement `fetch_records()` and `health_check()`
- **R2**: Records conform to unified schema
- **R3**: Health checks are cached for 30 seconds
- **R4**: Parse errors are counted, not crashed

The Access contract test runs with both readers (`access-parser`, `mdbtools`); the
`mdbtools` case and the reader-equivalence tests (`test_access_readers.py`) are
skipped when `mdb-export` is not installed.

### Property-Based Tests (`test_properties.py`, `test_normalizer.py`)

Uses Hypothesis to validate properties from `Roadmap.md §7`:

- **P1** Provenance conservation: all emitted data comes from source records
- **P2** Normalization idempotence: `norm(norm(x)) == norm(x)`
- **P3** Parser round-trip: parsing preserves message content
- **P4** Determinism: same inputs → same outputs
- **P6** No fabrication: no invented field values

### Engine and Schema Tests

- `test_interpreter.py`: runs `r_low_stock` on in-memory records (provenance, threshold, time window, incompatible types, best-match choice among duplicates, template rendering without brace expansion)
- `test_normalizer.py`: also checks that different numbers never match (`50 kg` vs `40 kg`) and that decimals and fractions stay one token
- `test_api_correlations.py`: uses the `api_client` fixture (fresh in-memory database, application lifespan, predefined rules seeded) with the file connectors replaced by in-memory records. Foreign keys are enforced on SQLite, so these tests fail the way PostgreSQL would

- `test_schemas.py`: rejects empty joins, Excel joins without `sheet`, Access joins without `table`, unknown operators
- `test_connector_payloads.py`: payload keeps the source column names, MoMo emits a `product` entity, invalid rows are skipped and counted

Test names follow "should [result] when [condition]" for new tests.

## Configuration

Test configuration in `pytest.ini`:

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
addopts = --hypothesis-profile=dev
```

Hypothesis profiles are registered in `tests/conftest.py`:

| Profile | `max_examples` | `deadline` |
|---------|----------------|------------|
| `dev` (default) | 100 | none |
| `ci` | 500 | 5000 ms |

For CI/CD:

```bash
python -m pytest tests/ --hypothesis-profile=ci
```

## Test Data

Tests use synthetic data from `data/` directory:

- `data/commandes_clients.txt` — WhatsApp export
- `data/momo_transactions.csv` — Mobile Money CSV (50 transactions)
- `data/tarifs_fournisseurs.xlsx` — Excel price list
- `data/STOCK_ZOBO.mdb` — Access database (24 articles)

Regenerate missing files:

```bash
# From project root
python scripts/generate_excel.py
python scripts/generate_momo.py
cscript //Nologo scripts/generate_access_windows.vbs  # Windows with Access only
```

The VBS script must stay ASCII-only (cscript reads it as ANSI): accented letters
are written as `\xHH` and decoded with `ChrW`.

## Environment

`tests/conftest.py` sets these variables before the application is imported,
so no `.env` file is needed:

| Variable | Test value |
|----------|------------|
| `BACKEND_NODE_ENV` | `test` (Redis not required) |
| `DATA_DIR` | `<repo>/data` |
| `DATABASE_URL` | `sqlite://` (in-memory) |
| `CORS_ORIGINS` | `http://localhost:3000` |
| `ACCESS_READER` | `access-parser` (the mdbtools reader is built explicitly in tests) |

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

### `ValueError: Required environment variable '...' is not set`

You are importing the application outside pytest. Export the variables listed in
`backend/README.md` (Setup, step 2) or run the tests through `python -m pytest`.

### Test data files not found

Generate synthetic data:

```bash
python scripts/generate_momo.py
python scripts/generate_excel.py  # requires openpyxl
```

---

_Last updated: 2026-11-13_
