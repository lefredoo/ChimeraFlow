# Technical Debt

Issues identified but not resolved in the current cycle.
Required by AGENTS.md §15.

---

## Format

[YYYY-MM-DD] Problem description | Estimated impact (low/med/high) | Concerned file(s)

---

## Current Debt

- [2026-11-13] Savepoint partial-rollback path untested: test_should_keep_previous_correlations_when_a_rule_fails raises before any DML | Low | backend/tests/test_api_correlations.py
- [2026-11-13] Seeding idempotence test counts rows but doesn't assert version == 1 after re-seed | Low | backend/tests/test_api_correlations.py
- [2026-11-13] models/seed.py change detection relies on JSON round-trip equality; a future Enum field would bump version on every restart | Low | backend/models/seed.py

### [2026-11-13] 3 predefined rules inactive pending DSL trigger-side where decision | Medium | backend/engine/predefined_rules.py, backend/models/seed.py

**Problem**: `r_payment_received` (ignores the PENDING status, joins WhatsApp on free text), `r_price_comparison` (the DSL cannot compute a > 10% gap) and `r_stock_replenish` (no where on the trigger record, so stock < 15 is not checked) contradict their own description. They are seeded `inactive` and never executed.

**Impact**: Medium - 3 of the 5 predefined rules do nothing. `r_low_stock` and `r_high_value_order` stay active.

**Solution**: Decide whether the DSL gets a where on the trigger record, a computed comparison, and a join on the entities of the joined record. Then fix the rules and activate them. Reversible: seeding keeps an operator's status choice.

---

### Residual review findings (not fixed, non-blocking)

- [2026-11-13] Time window is symmetric for every source, so a WhatsApp message can match a stock or price record dated after it | Low | backend/engine/interpreter.py
- [2026-11-13] Only the first entity of a message is correlated (a message with two products yields one correlation) | Medium | backend/engine/interpreter.py
- [2026-11-13] Dead synonym entries ("50kg" never survives normalization, "l" maps to "litre" for any word "l") | Low | backend/engine/normalizer.py
- [2026-11-13] Schema bounds missing: `on.field` not required, no `max_length` on `emit.template`, `where` list or `where.value` | Medium | backend/schemas/rule.py
- [2026-11-13] Performance: normalized names are recomputed for every record pair (precompute once per run); sync SQLAlchemy and connector I/O block the event loop in `async def` handlers (use `asyncio.to_thread` or plain `def`) | Medium | backend/engine/interpreter.py, backend/api/correlations.py, backend/api/rules.py
- [2026-11-13] `CONNECTOR_ERRORS` lacks `csv.Error`, `zipfile.BadZipFile` and `openpyxl` `InvalidFileException`; connector `parse_errors` is never reset between fetches | Medium | backend/mcp_servers/base.py, backend/mcp_servers/*.py
- [2026-11-13] Missing tests: connector parse-error tests (connectors.md), API tests for rules endpoints, property tests P1, P4, P5, P6 on the interpreter, operator tests (`eq`, `ne`, `lte`, `gte`, `contains`, `in`) and window-boundary tests | Medium | backend/tests/
- [2026-11-13] `rules.created_by` stores the client IP address (personal data) | Medium | backend/api/rules.py, backend/models/rule.py
- [2026-11-13] Source text is not sanitized backend-side; the frontend must escape messages and payload values before display (security.md rule 2) | Medium | backend/engine/interpreter.py
- [2026-11-13] `DELETE /rules/{id}` accepts a predefined rule id; the rule comes back at the next startup (the id stays reserved for `POST /rules`) | Low | backend/api/rules.py

---

### [2026-11-13] Documentation decisions pending (language of user docs, missing tasks.md/design.md/api-spec.md, rule-validate hook target, LICENSE owner) — see docs/decisions/p2-decisions-qcm.html | Low | README.md, Roadmap.md, AGENTS.md, .kiro/hooks/rule-validate.json

**Problem**: Several documentation decisions are still open and recorded in a questionnaire: language of user docs, missing `tasks.md`, `design.md` and `api-spec.md` specs, target of the `rule-validate` hook, and LICENSE owner.

**Impact**: Low - documentation can drift until the answers are applied.

**Solution**: Answer the questionnaire, then apply the answers to the listed files.

---

### [2026-11-13] Rate limiting and NL→rule conversion not implemented | High | backend/api/rules.py, backend/config.py

**Problem**: P2 scope includes per-IP rate limiting and LiteLLM NL→JSON conversion (2 retries, budget cap). Neither exists. `RATE_LIMIT_*` and `LITELLM_*` variables are read by `config.py` but unused.

**Impact**: High - `POST /api/v1/rules` is open to unlimited creation (security.md rule 4); the NL input of the UI has no backend.

**Solution**: Add `slowapi` and `litellm` once the product owner approves the dependencies (AGENTS.md §16).

---

### [2026-11-13] Access source unreadable on Windows | Medium | backend/mcp_servers/access_connector.py

**Problem**: `AccessConnector` calls `mdb-export` (mdbtools), which is not available on Windows. On the dev machine `GET /api/v1/sources/access/records` fails and `r_low_stock` (the only active rule that joins `access`) emits nothing. The Access contract test is skipped without mdbtools.

**Impact**: Medium - the demo rule cannot be checked end to end on Windows. Works in the Docker image (installs mdbtools).

**Solution**: Run the demo through Docker, or switch to a pure Python reader (`access-parser`, dependency pending approval).

---

### [2026-11-13] Entity matching is whole-string, so partial product names do not match | Medium | backend/engine/interpreter.py, backend/engine/normalizer.py

**Problem**: `EntityNormalizer.match` compares the full normalized strings with `difflib` (threshold 0.85), after requiring the same numbers on both sides ("ciment 50 kg" never matches "ciment 40 kg"). "perceuse 500W" vs "Perceuse électrique 500W" scores 0.72 and "tuyau PVC" vs "Tuyau PVC Ø 32mm (barre 6m)" scores 0.50, so only products written in full (the "ciment 50 kg" scenario) correlate. On the real data files, `r_high_value_order` finds nothing.

**Impact**: Medium - the 4-variants demo works, other products do not.

**Solution**: Decide the matching strategy (token containment, `rapidfuzz` token-set ratio, or richer WhatsApp extraction). `rapidfuzz` needs product owner approval.

---

### [2026-11-13] Environment variable names differ between code and deployment files | Medium | backend/config.py, docker-compose.yml, AGENTS.md §22

**Problem**: `config.py` reads `BACKEND_PORT`, `BACKEND_LOG_LEVEL`, `BACKEND_NODE_ENV`. `docker-compose.yml` sets `PORT` and `LOG_LEVEL`, and AGENTS.md §22 lists `NODE_ENV`, `PORT`, `LOG_LEVEL`. In Docker the two settings are silently ignored.

**Impact**: Medium - misleading configuration. Renaming is pending a decision, so the names were left unchanged.

**Solution**: Choose one naming scheme and align `config.py`, `docker-compose.yml`, Doppler and AGENTS.md.

---

### [2026-11-13] requirements.txt pins differ from the versions used by the tests | Medium | backend/requirements.txt

**Problem**: Tests run on pydantic 2.13, pandas 3.0, pytest 9 while `requirements.txt` pins pydantic 2.5.0, pandas 2.1.3, pytest 7.4.3. `psycopg` (PostgreSQL driver for Neon) is not listed. The Docker image installs the pinned versions.

**Impact**: Medium - behavior validated locally may differ in the image.

**Solution**: Decide the pins (re-pin to tested versions or test on the pinned ones) and add the PostgreSQL driver.

---

### [2026-11-13] Dockerfile healthcheck depends on a package that is not installed | Low | backend/Dockerfile

**Problem**: The `HEALTHCHECK` runs `import requests`, and `requests` is not in `requirements.txt`. `docker-compose.yml` overrides it with `curl`, which `python:3.11-slim` does not include.

**Impact**: Low - containers can report unhealthy while the API runs.

**Solution**: Use `python -c "import urllib.request; ..."` in both places.

---

### [2026-11-13] Predefined rule templates are hardcoded French text with emoji | Low | backend/engine/predefined_rules.py

**Problem**: `natural_language` and `emit.template` of predefined rules are literal French strings (AGENTS.md §4, §8: user-visible text belongs in i18n files).

**Impact**: Low - the API returns French only.

**Solution**: Move texts to i18n resources with FR and EN keys once the frontend i18n layer exists.

---

### [2026-11-13] Source timestamps without offset are treated as UTC | Low | backend/engine/interpreter.py

**Problem**: WhatsApp, Excel, Access and MoMo timestamps carry no timezone. The interpreter reads them as UTC. The demo business is in Douala (UTC+1), so the window is shifted by one hour at most.

**Impact**: Low - negligible for windows of one day or more.

**Solution**: Add a source timezone setting when windows shorter than a few hours are needed.

---

### [2026-11-13] WhatsApp parser limits | Low | backend/mcp_servers/whatsapp_connector.py

**Problem**: Product extraction uses a hardcoded keyword list (ciment, pointe, vis, tuyau, ...). Multi-line messages and non-Android export formats are counted as parse errors (R6 of connectors-spec.md asks for both).

**Impact**: Low - sufficient for the demo data, does not generalize.

**Solution**: Handle continuation lines and the iOS format; LLM-assisted extraction once LiteLLM is available.

---

### [2026-11-13] No Alembic migrations | Low | backend/models/base.py

**Problem**: Tables are created with `Base.metadata.create_all` at startup. Alembic is in `requirements.txt` but not configured.

**Impact**: Low - fine for the demo, schema changes need manual work on an existing database.

**Solution**: Initialize Alembic before the first production schema change.

---

### [2026-11-13] No containerization for MCP servers yet | Medium | backend/

**Problem**: P1 focused on connector logic. Docker Compose exists but MCP server container not yet configured.

**Impact**: Medium - deployment to VPS Hetzner will need container setup.

**Solution**: P3 task (Docker integration).

---

_Add new entries at the top of this file (reverse chronological order)._
