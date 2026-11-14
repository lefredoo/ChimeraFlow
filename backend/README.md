# ChimeraFlow Backend

FastAPI backend for the correlation engine.

## Architecture

```
backend/
├── api/                    # REST API endpoints
│   ├── sources.py          # GET /sources (P1)
│   ├── rules.py            # POST /rules, GET /rules
│   └── correlations.py     # POST /correlations/execute, GET /correlations
├── engine/                 # Rule engine (P2)
│   ├── interpreter.py      # Rule interpreter (trigger, joins, where, emit)
│   ├── normalizer.py       # Normalization (single implementation) + fuzzy match + synonyms
│   └── predefined_rules.py # 5 predefined rules (3 seeded inactive)
├── mcp_servers/            # Data source connectors (P1)
│   ├── base.py             # BaseConnector + UnifiedRecord schema
│   ├── excel_connector.py  # Excel reader (pandas + openpyxl)
│   ├── access_connector.py # Access reader (mdbtools CLI or access-parser, ACCESS_READER)
│   ├── whatsapp_connector.py # WhatsApp parser (regex)
│   └── momo_connector.py   # Mobile Money CSV reader
├── migrations/             # Alembic migrations (env.py reads DATABASE_URL)
├── models/                 # SQLAlchemy models (P2)
│   ├── base.py             # Database configuration (SQLite foreign keys enabled)
│   ├── rule.py             # Rule, RuleExecution, Correlation
│   └── seed.py             # Idempotent seeding of predefined rules at startup
├── schemas/                # Pydantic validation (P2)
│   └── rule.py             # RuleCreate, RuleResponse, etc.
├── tests/                  # Tests
│   ├── conftest.py         # Test environment variables, Hypothesis profiles, api_client fixture
│   ├── factories.py        # In-memory unified records for engine and API tests
│   ├── test_api_correlations.py # Seeding, execution, foreign keys, idempotence
│   ├── test_connectors.py  # Contract tests (R1-R4)
│   ├── test_connector_payloads.py # Source field names, entities, parse errors
│   ├── test_properties.py  # Property-based tests (Hypothesis)
│   ├── test_normalizer.py  # Normalization variants, idempotence, numeric tokens
│   ├── test_interpreter.py # Rule execution, provenance, best-match choice, template rendering
│   ├── test_schemas.py     # Rule schema validation
│   └── test_health.py      # API smoke tests
│   ├── test_access_readers.py # mdbtools and access-parser produce identical records
│   ├── test_migrations.py  # alembic upgrade head / downgrade base, drift with the models
├── config.py               # Environment configuration
├── main.py                 # FastAPI application
├── alembic.ini             # Alembic configuration
├── requirements.txt        # Runtime dependencies (Python 3.13)
└── requirements-dev.txt    # Test and lint tools
```

## Setup

### 1. Install dependencies

Python 3.13 virtual environment with [uv](https://docs.astral.sh/uv/) (git-ignored .venv):

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt   # Windows: .venv\Scripts\python.exe
```

### 2. Configure environment

The backend reads environment variables only (no `.env` loader). In production
they come from Doppler. For local development, export them in your shell.
Missing required variables stop the application at startup, by design
(AGENTS.md §7).

**Required**

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy connection string (PostgreSQL on Neon in production) |
| `CORS_ORIGINS` | Comma-separated list of allowed origins |
| `DATA_DIR` | Directory containing the synthetic data files |
| `REDIS_URL` | Redis connection (not required when `BACKEND_NODE_ENV=test`) |
| `ACCESS_READER` | `mdbtools` (Docker, production) or `access-parser` (pure Python, local Windows). Any other value stops the startup |

**Optional** (the related behavior is disabled or left to the library default when unset)

| Variable | Purpose |
|----------|---------|
| `BACKEND_NODE_ENV` | `development`, `production` or `test` |
| `BACKEND_PORT` | Port used by `python main.py` (uvicorn default when unset) |
| `BACKEND_LOG_LEVEL` | Logging level |
| `RATE_LIMIT_PER_IP`, `RATE_LIMIT_WINDOW_SECONDS` | Rate limiting (not enforced yet) |
| `LITELLM_API_KEY`, `LITELLM_BUDGET_USD` | NL→rule conversion (not implemented yet) |

Example (PowerShell):

```powershell
$env:DATABASE_URL = "postgresql://user:pass@host/dbname"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:DATA_DIR = "../data"
$env:ACCESS_READER = "access-parser"
```

### 3. Generate synthetic data

```bash
# From project root
python scripts/generate_excel.py
python scripts/generate_momo.py              # seeded: same output on every run
cscript scripts/generate_access_windows.vbs  # Windows only
```

### 4. Create the schema and run the server

The schema is managed by Alembic. The container entrypoint runs the migration;\nlocally, run it once (and after each new revision) before starting the server:

```bash
python -m alembic upgrade head
python -m uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## API Endpoints

### Sources (P1)

```
GET  /api/v1/sources              # List all sources
GET  /api/v1/sources/{source}/health  # Health check
GET  /api/v1/sources/all/records      # Fetch from all sources
GET  /api/v1/sources/{source}/records # Fetch records (limit param)
```

### Rules (P2)

```
GET  /api/v1/rules/predefined    # List the 5 predefined rules (stored status)
POST /api/v1/rules                # Create new rule (validated; 409 if the id exists or is predefined)
GET  /api/v1/rules                # List all rules (filter by status)
GET  /api/v1/rules/{id}           # Get specific rule
DELETE /api/v1/rules/{id}         # Delete rule and its correlations
```

### Correlations (P2)

```
POST /api/v1/correlations/execute # Execute active rules (query: rule_ids, max 20)
GET  /api/v1/correlations         # List correlations (filter by rule_id, severity; limit 1 to 1000)
```

`execute` runs active rules only (inactive and draft rules are skipped) and
**replaces** the previous correlations of each rule it runs, so executing twice
gives the same list. The response reports `rules_executed`, `rules_failed`,
`correlations_found`, `records_scanned` and `duration_ms`. A failing rule keeps
its previous correlations; `rule_executions.error` holds a generic message and
the details go to the logs. `detected_at` is set by the API, not by the engine.

## Source Records

Every connector returns `UnifiedRecord` objects (AGENTS.md §19). The payload
keeps the **original column names of the source**, so a rule's `field` and
`{source.field}` template placeholders refer to what the user sees in the
source file.

| Source | Payload fields | Record timestamp | Entities |
|--------|----------------|------------------|----------|
| `excel` | `Produit`, `Prix_Unitaire`, `Fournisseur`, `Date_MAJ` | `Date_MAJ` | `product` |
| `access` | `id`, `designation`, `unite`, `qty_stock`, `prix_achat`, `date_modif` | `date_modif` | `product` |
| `whatsapp` | `author`, `text` | message date | `product` (keyword + quantity, e.g. `ciment 50kg`) |
| `momo` | `transaction_id`, `timestamp`, `phone`, `customer_name`, `operator`, `amount`, `currency`, `status`, `reference`, `quantity` | `timestamp` | `payment`, `product` (from `reference`) |

Rows that cannot be parsed (missing product, invalid date, invalid quantity or
amount) are skipped, logged and counted in the connector's `parse_errors`.
Values are never invented, so the same files always give the same records (P4).

## Rule Schema

Rules follow AGENTS.md §20 format:

```json
{
  "id": "r_low_stock",
  "natural_language": "Quand un client demande un produit sur WhatsApp...",
  "trigger": {
    "source": "whatsapp",
    "entity": "product"
  },
  "joins": [
    {
      "source": "access",
      "table": "Articles",
      "on": {"entity": "product", "field": "designation"},
      "where": [{"field": "qty_stock", "op": "lt", "value": 10}]
    }
  ],
  "window_seconds": 604800,
  "emit": {
    "severity": "warning",
    "template": "{product}: stock {access.qty_stock}, prix {excel.Prix_Unitaire} FCFA"
  }
}
```

Validation rules: 1 to 10 joins; an `access` join needs `table`; an `excel`
join needs `sheet`.

**Allowed operators** (security whitelist):
- `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`

## Rule Engine

### Interpreter (`engine/interpreter.py`)

- Executes rules against unified records
- Time window: a joined record must be within `window_seconds` **before or after**
  the trigger record (reference data such as prices usually predates the message)
- Tracks provenance (P1 property): every correlation lists the trigger record and each joined record
- Only allows whitelisted operators (R5)
- A `where` comparison between incompatible types (e.g. text vs number) is a non-match, not an error
- Deterministic (P4 property): the output depends on the inputs only (no detection time)
- When several records of a joined source match, the best one is chosen: highest
  similarity score, then a record at or before the trigger, then the closest in time
  (the latest price wins among duplicates), then source order
- Templates are rendered in one pass: source text that looks like `{momo.phone}` is not
  expanded, and a placeholder without a value renders as an empty string
- Source timestamps without offset are interpreted as UTC

### Normalizer (`engine/normalizer.py`)

`normalize_text()` is the single normalization implementation; connectors call
it through `BaseConnector.normalize_text()`. Steps, in order:

1. Lowercase
2. Remove accents
3. Keep decimals and fractions as one token (`2.5` becomes `2-5`, `1/2` becomes `1-2`)
4. Remove punctuation (hyphens kept)
5. Split letters from digits (`50kg` becomes `50 kg`)
6. Collapse whitespace (last, so that the result is idempotent: P2)

Matching adds FR/EN synonyms and fuzzy similarity (`difflib.SequenceMatcher`,
threshold 0.85). Two entities only match when they contain the same numbers:
`ciment 50 kg` never matches `ciment 40 kg`, even though their similarity is 0.92.

Example:
```python
from engine.normalizer import normalize_text

# The demo scenario: one product written four ways
normalize_text("ciment 50 kg")   # "ciment 50 kg"
normalize_text("Ciment50kg")     # "ciment 50 kg"
normalize_text("cimént 50kg")    # "ciment 50 kg"
normalize_text("ciment (50kg)")  # "ciment 50 kg"
```

### Predefined Rules (`engine/predefined_rules.py`)

5 rules as per Roadmap:

1. **r_low_stock**: Low stock alert (demo rule), active
2. **r_payment_received**: Payment confirmation, **inactive**
3. **r_price_comparison**: Price discrepancy detection, **inactive**
4. **r_high_value_order**: High-value order tracking, active
5. **r_stock_replenish**: Replenishment recommendation, **inactive**

Rules 2, 3 and 5 are seeded inactive because the DSL cannot express what their
description promises (status filter, > 10% gap, stock threshold on the trigger
record). Activating one is a status change in the `rules` table; the seeding
keeps that choice on restart. See `docs/decisions/TECH_DEBT.md`.

## Database

SQLAlchemy models:

- **Rule**: Correlation rule definition
- **RuleExecution**: Execution history (duration, records scanned)
- **Correlation**: Emitted correlation with provenance

`DATABASE_URL` is required (no SQLite fallback). PostgreSQL (Neon) in
production. Tables are created and the predefined rules are upserted into
`rules` at startup; startup fails if either is not possible. Correlations and
executions reference `rules.id` with `ON DELETE CASCADE`, so deleting a rule
deletes its results. Foreign keys are also enforced on SQLite (tests behave like
PostgreSQL). Each rule runs inside its own savepoint, so a failing rule leaves
no partial correlations. Timestamps are stored as timezone-aware UTC.

## Testing

Run from `backend/`. `tests/conftest.py` sets the test environment variables
(`BACKEND_NODE_ENV=test`, `DATA_DIR`, in-memory SQLite `DATABASE_URL`,
`CORS_ORIGINS`), so no `.env` file is needed.

```bash
# All tests
python -m pytest tests/ -v

# Contract tests (R1-R4)
python -m pytest tests/test_connectors.py -v

# Property-based tests (Hypothesis)
python -m pytest tests/test_properties.py tests/test_normalizer.py -v
```

The Access contract test is skipped when `mdb-export` (mdbtools) is not installed.

## Security

Per AGENTS.md §1 (security guidelines):

- Implemented: **no code execution** (rules are JSON, interpreted with whitelisted operators)
- Implemented: **input validation** with strict Pydantic schemas
- Implemented: source error details are logged, not returned in HTTP responses
- Implemented: source text is clearly separated from instructions (no LLM involved yet)
- Not implemented yet: **rate limiting** per IP on rule creation
- Not implemented yet: **LLM budget cap** (NL→rule service does not exist yet)
- Not implemented yet: **sanitization** of source text before display (frontend work)

## Development

### Adding a new connector

1. Create `backend/mcp_servers/my_connector.py`
2. Extend `BaseConnector`
3. Implement `fetch_records()` and `_perform_health_check()`
4. Return `UnifiedRecord` objects with the source's original column names in the payload
5. Add tests in `tests/test_connectors.py`

### Adding a new rule

Use API or add to `engine/predefined_rules.py`:

```python
RuleCreate(
    id="r_my_rule",
    natural_language="...",
    trigger=RuleTrigger(source="whatsapp", entity="product"),
    joins=[...],
    window_seconds=604800,
    emit=RuleEmit(severity="warning", template="...")
)
```

---

**Phase**: P2 (Moteur de règles) — in progress (interpreter, normalizer, rules and correlations API done; NL→rule and rate limiting pending)
