# Technical Debt

Issues identified but not resolved in the current cycle.
Required by AGENTS.md §15.

---

## Format

[YYYY-MM-DD] Problem description | Estimated impact (low/med/high) | Concerned file(s)

---

## Current Debt

### [2026-11-13] Python dependencies not installed on user machine | Medium | backend/requirements.txt

**Problem**: requirements.txt includes pytest, pytest-asyncio, hypothesis but these are not installed on user's Python installation. Tests cannot run without `pip install -r backend/requirements.txt`.

**Impact**: Medium - tests are written and ready but cannot verify connector behavior without installation.

**Solution**: User must run `pip install -r backend/requirements.txt` before running tests or CI/CD pipeline.

---

### [2026-11-13] Excel synthetic data file not generated | Medium | data/tarifs_fournisseurs.xlsx

**Problem**: `scripts/generate_excel.py` exists but requires openpyxl installation. File not generated yet.

**Impact**: Medium - ExcelConnector cannot be tested with real file until generated.

**Solution**: Run `pip install openpyxl` then `python scripts/generate_excel.py` to generate file.

---

### [2026-11-13] Access .mdb file not generated | Medium | data/STOCK_ZOBO.mdb

**Problem**: `scripts/spike_access.py` exists for investigation but Access database file not yet generated. Requires either Windows with Access, Jackcess (Java), or mdbtools on Linux.

**Impact**: Medium - AccessConnector cannot be tested with real file until generated.

**Solution**: 
- Option 1: Windows machine with Access (manual creation or script)
- Option 2: Use Jackcess (Java library) to generate .mdb programmatically
- Option 3: Use mdbtools on Linux to create and populate database

---

### [2026-11-13] WhatsApp parser uses simple keyword matching | Low | backend/mcp_servers/whatsapp_connector.py

**Problem**: Entity extraction in `_extract_products()` uses hardcoded keyword list instead of NLP/LLM-based extraction.

**Impact**: Low - sufficient for demo with known products, but won't generalize to new products.

**Solution**: Deferred to P2 (Rule Engine) where LiteLLM integration will enable better entity extraction.

---

### [2026-11-13] No containerization for MCP servers yet | Medium | backend/

**Problem**: P1 focused on connector logic. Docker Compose exists but MCP server container not yet configured.

**Impact**: Medium - deployment to VPS Hetzner will need container setup.

**Solution**: P3 task (Docker integration), after P2 (Rule Engine).

---

_Add new entries at the top of this file (reverse chronological order)._
