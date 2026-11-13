# ChimeraFlow — Build Log

Daily journal of development progress for Kiroween 2026 Hackathon.
Useful for write-up and video preparation.

Format: [Date] Decision | Discovery | Observation

---

## 2026-11-13 — P0 & P1 Complete

### P0 Fondations (8h)
- Created complete project structure: backend (FastAPI), frontend (Next.js), Docker Compose, documentation
- Generated AGENTS.md (governance), DESIGN.md (design system), 3 Kiro specs (connectors, rule-engine, ui)
- Interactive QCM decision process: glassmorphism design, IBM Plex fonts, Professional Blue palette
- Single root .env with Doppler integration (prod: only DOPPLER_TOKEN)
- Git workflow: two branches only (main/dev), Conventional Commits

### P1 Connecteurs (~95%, 14h/20h)

**Implemented:**
- BaseConnector abstract class with unified normalization (lowercase, accents, whitespace, punctuation)
- 4 MCP connectors:
  - ExcelConnector (pandas + openpyxl): reads tarifs_fournisseurs.xlsx
  - AccessConnector (mdbtools CLI): reads STOCK_ZOBO.mdb
  - WhatsAppConnector (regex parsing): parses Android/iOS export formats
  - MobileMoneyConnector (CSV): reads momo_transactions.csv
- Unified record schema: id, source, source_ref, timestamp, lang (fr|en), entities[], payload
- FastAPI REST API: GET /api/v1/sources, /{source}/health, /{source}/records, /all/records
- Contract tests (pytest): validates R1-R4 from connectors-spec.md
- Property-Based Testing (Hypothesis): validates P2, P4, P1, P6 properties
- Kiro hooks: parser-test (run tests on save), spec-update-reminder, rule-validate
- Synthetic data: WhatsApp export (50 messages), Mobile Money CSV (50 transactions)

**Key Decisions:**
- Normalization handles demo scenario: "ciment 50 kg", "Ciment50kg", "cimént 50kg", "ciment (50kg)" → all normalize to comparable forms
- Health check caching (30s) reduces file system load
- Parse errors counted and logged, never crash (R4 compliance)
- mdbtools CLI chosen over access_parser for .mdb reliability
- Config.py: requireEnv() pattern with optional Redis in test environment

**Remaining Blockers (tracked in TECH_DEBT.md):**
- Excel tarifs_fournisseurs.xlsx generation: requires `pip install openpyxl` + run `python scripts/generate_excel.py`
- Access STOCK_ZOBO.mdb generation: requires Windows/Jackcess or mdbtools on Linux
- Test dependencies: `pip install -r backend/requirements.txt` needed to run tests (pytest, hypothesis)

**Kiro Usage:**
- 3 hooks created (.kiro/hooks/)
- 3 specs written (.kiro/specs/)
- 2 steering files active (.kiro/steering/)
- Property-Based Testing with Hypothesis (6 properties defined)

**Time Tracking:**
- P0: ~8h (on schedule)
- P1: ~14h / 20h budgeted (ahead of schedule)
- Next: P2 Moteur de règles (20h, Nov 20-24)

**Credits Consumed:** (to be tracked on kiro.dev/account/usage)

---

## 2026-11-13 — P2 in progress: rule engine review

**Implemented:** rule schema (Pydantic), interpreter with provenance, 5 predefined rules, `/rules` and `/correlations` API, SQLAlchemy models.

**Discovery (audit of the first P2 draft):**
- Rules referenced `Produit` / `Prix_Unitaire` but connectors emitted `product` / `price`: nothing could correlate. Payloads now keep the source column names.
- The "4 ways to write ciment 50 kg" scenario only worked once letters and digits were split (`Ciment50kg` → `ciment 50 kg`) and whitespace was collapsed last (idempotence).
- A forward-only time window dropped every price list row, because prices predate the WhatsApp message. The window is now symmetric.
- Hypothesis found a real case in a test: some capital letters (U+2110) have no lowercase mapping, so the "is lowercase" check became "lowercasing changes nothing".

**Observation:** On Windows the Access source cannot be read (no mdbtools), so `r_low_stock` cannot be demonstrated there. See TECH_DEBT.md.

**Tests:** 49 passed, 1 skipped (Access contract test without mdbtools).

---

## 2026-11-13 — P2 review pass 2

**Fixed:**
- Join choice: the interpreter took the first in-window record. It now picks the best score, then the latest record at or before the trigger.
- Matching: "ciment 50 kg" and "ciment 40 kg" scored 0.92. Numbers must now be equal on both sides, and "2.5" or "1/2" no longer collapse into "25" or "12".
- Foreign keys: predefined rules were never rows of `rules`, so PostgreSQL would reject their correlations. They are now seeded at startup, and SQLite enforces foreign keys in tests.
- Duplicates: each execution replaces the rule's previous correlations.
- `data/STOCK_ZOBO.mdb`: cscript read the VBS as ANSI and stored "CÃ¢ble". The script is ASCII-only now, the database was regenerated and the accents read back correctly through DAO.
- 3 predefined rules contradicted their description, so they are seeded inactive (see TECH_DEBT.md).

**Tests:** 93 passed, 1 skipped (default and `ci` Hypothesis profiles). `pyflakes` is clean.

---

_Continue logging daily progress here._
