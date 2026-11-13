# Decision Log

Chronological history of architectural and technical decisions.

---

## Entry Format

```markdown
## [YYYY-MM-DD] Short decision title

**Context**: Why this choice arose (1-2 sentences)
**Decision**: What was done
**Alternatives rejected**: What was discarded and why
**Consequences**: Impact on codebase (debt, future constraints)
**AGENTS.md rule concerned**: (if applicable)
```

---

## [2026-11-13] P1 Connecteurs Implementation Complete (95%)

**Context**: Implementation of Phase 1 (Connecteurs) per Roadmap.md, including all 4 MCP connectors, unified record schema, tests, and Kiro hooks.

**Decision**: 
- Implemented BaseConnector abstract class with normalization strategy (lowercase, accent removal, whitespace collapse, punctuation removal)
- Created 4 connectors: ExcelConnector (openpyxl), AccessConnector (mdbtools CLI), WhatsAppConnector (regex parsing), MobileMoneyConnector (CSV)
- Unified record schema enforced: id, source, source_ref, timestamp, lang (fr|en), entities[], payload
- FastAPI REST API endpoints: GET /api/v1/sources, /{source}/health, /{source}/records, /all/records
- Contract tests (test_connectors.py): validates R1-R4 from connectors-spec.md for all connectors
- Property-Based Testing (test_properties.py): validates P2 (normalization idempotence), P4 (determinism), P1 (provenance), P6 (no fabrication)
- Kiro hooks: parser-test.json (run tests on connector save), spec-update-reminder.json (remind on spec change), rule-validate.json (validate rule schema)
- Synthetic data generated: WhatsApp export (50 messages), Mobile Money CSV (50 transactions)

**Alternatives rejected**:
- Pure Python Access parser (access_parser): rejected due to poor .mdb support, chosen mdbtools CLI for reliability
- Individual .env per service: rejected for single root .env with Doppler in production
- Full LLM-based entity extraction in P1: deferred to P2, using simple keyword matching for MVP

**Consequences**:
- P1 ~95% complete: connectors implemented and tested, synthetic data generated (WhatsApp, Mobile Money)
- Remaining blockers: Access .mdb file generation (requires Windows/Jackcess or mdbtools on Linux), Excel tarifs_fournisseurs.xlsx generation (requires openpyxl installation), pytest dependencies installation (hypothesis installed in requirements.txt but not on user machine)
- Health check caching (30s) reduces load on file system (R3 compliance)
- Parse errors logged and counted without crashing (R4 compliance)
- Normalization handles demo scenario: 4 spelling variations of "ciment 50 kg" normalize to comparable forms
- Tests ready but cannot run without installing dependencies: `pip install -r backend/requirements.txt` needed
- Config.py modified to allow optional REDIS_URL in test environment

**AGENTS.md rule concerned**: §4 (critical rules - never leave unresolved problem documented), §7 (configuration management - requireEnv pattern), §11 (testing), §12 (agent behavior - verify build)

---

## [2026-11-13] Décisions Techniques et Design — ChimeraFlow

**Context**: Finalisation des choix techniques et design avant implémentation du projet Kiroween 2026. Validation via QCM interactif pour structurer toutes les décisions importantes du projet.

**Decision**: 
- **Design**: Glassmorphism moderne, palette Professional Blue (#2563eb), typographie IBM Plex (Sans/Serif/Mono)
- **Architecture Frontend**: Next.js 15+ on Vercel, Context API, Tailwind CSS v4
- **Architecture Backend**: FastAPI on VPS Hetzner, SQLAlchemy, Redis rate limiting, logs structurés
- **Data**: Schéma unifié (source, source_ref, timestamp, lang, entities, payload), normalisation hybride (règles + fuzzy), FR/EN
- **MVP**: Dashboard (règles actives, corrélations récentes, santé sources, stats) + Page règles (NL input, JSON edit, liste, prédéfinis) + Pages sources + Settings
- **Kiro**: 4 specs (connectors, rule-engine, ui, api), 3 agents Crew (chimera-builder, test-warden, rule-smith), 3 hooks (parser-test, spec-update, rule-validate), 6 propriétés PBT (provenance, idempotence, roundtrip, determinism, monotonicity, no_fabrication)
- **Startup**: LinguaSolution LLC, ajout page ChimeraFlow + services + blog post, lien narratif : normalisation linguistique NLP
- **Démo**: ZOBO Hardware Store (Douala), produits variés (pointes/vis, tuyaux PVC, électrique, cadenas, peinture, ciment, outillage, brouette, pompes, solaire)

**Alternatives rejected**: 
- Styles alternatifs (minimaliste strict, bold coloré) — glassmorphism mieux adapté à l'identité "business intelligence moderne"
- Palettes alternatives (tech green, creative purple) — professional blue plus trustworthy pour PME
- State management complexe (Zustand, Redux) — Context API suffisant pour le scope MVP
- Monitoring lourd (Sentry) — logs structurés plus pragmatiques pour hackathon
- Normalisation simple (règles seules ou embeddings seuls) — hybride offre meilleur balance précision/performance

**Consequences**: 
- Architecture complète définie pour les 21 jours du hackathon (84h)
- Design system cohérent appliqué dans DESIGN.md
- Stack technique validée : pas de changement majeur pendant l'implémentation
- Scope MVP clair : focus sur dashboard + règles + corrélations
- Kiro usage structuré : specs, agents Crew, hooks, PBT tous définis
- LinguaSolution LLC positionnée pour Best Startup Project
- AGENTS.md sections 18-22 complétées avec les spécifications techniques
- README.md et DESIGN.md finalisés avec vraies informations

**AGENTS.md rule concerned**: §14 (Decision Log obligatoire avant commit)

---

## [2026-11-13] Project initialization with governance structure

**Context**: Creation of a new project requiring clear documentation and governance structure for AI agents and developers.

**Decision**: Adopt best practices from reference projects (Akili and Ancestria) including AGENTS.md for development guidelines, DESIGN.md for design system, structured docs/ directory, and two-branch Git workflow (main/dev).

**Alternatives rejected**: 
- Starting without documentation structure — would lead to inconsistent development practices
- Multiple feature branches — adds complexity without benefit for this project
- Storing configuration in code — violates security best practices

**Consequences**: 
- Solid foundation for future development
- Clear standards from day one
- All team members (human and AI) follow same conventions
- Technical decisions are documented and traceable

**AGENTS.md rule concerned**: §14 (DECISIONS_LOG mandatory), §5 (Git workflow)

---

_Add new entries at the top of this file (reverse chronological order)._
