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

## 2026-11-14 — Vagues 1 et 2 : documentation alignée sur le code

- Vagues 1 et 2 terminées. Contrôles : local 240 réussis, 3 sautés (Windows, sans mdbtools) ; Docker 243 réussis, 0 sauté (avec mdbtools).
- README, `docs/` et `backend/README.md` traduits en français et corrigés sur le code. Créés : `.kiro/specs/design.md` (propriétés P1 à P6 avec statut), `tasks.md` et `api-spec.md`.
- Décisions : documentation utilisateur en français ; `AGENTS.md` et `CLAUDE.md` restent en anglais ; licence MIT, LinguaSolution LLC.
- Blocage : la CI GitHub Actions ne démarre pas (facturation du compte, run 43569157569). Voir `TECH_DEBT.md`.
- Propriétés : P2 couverte ; P1, P4 et P6 partielles ; P3 et P5 non couvertes.

---

## 2026-11-15 — Déploiement, authentification, DSL étendu, interface

- Décisions : premier déploiement depuis `dev` (Vercel, VPS Dokploy/Traefik) avant la fusion de la PR ; compte de démonstration unique avec jeton signé par le backend ; DSL étendu (`trigger.where`, `ref` avec `tolerance_pct`, jointure sur `entities`) mais fermé, sans expression libre ; budget LLM réservé avant l'appel plutôt que compté après.
- Noms partiels : un nom contenu mot pour mot dans l'autre correspond (« tuyau PVC » dans « Tuyau PVC Ø 32mm (barre 6m) »), mais des nombres différents ne correspondent jamais. Une comparaison par `token_set_ratio` seule notait 0,9 deux produits différents (« tuyau pvc 32mm » et « tuyau ppr 32mm »).
- Ce que les tests de propriétés (Hypothesis) et l'exécution sur PostgreSQL avaient déjà révélé le 13 novembre reste la base du moteur : U+2110 (capitale sans minuscule) cassait l'idempotence de la normalisation, et les clés étrangères, ignorées par SQLite sans `PRAGMA foreign_keys`, exigent que le seed crée les règles prédéfinies au démarrage.
- Interface P3 livrée (tableau de bord, composeur, corrélations, bac à sable, flux SSE) ; première version des serveurs MCP en stdio.

---

## 2026-11-16 — E-mails d'alerte, alias LiteLLM, Traefik

- Décisions : délai global des e-mails d'alerte (`SET NX EX` dans Redis, échec fermé sans Redis) ; envoi par Cloudflare Email Service ; le modèle est l'alias nu du proxy LiteLLM, sans préfixe de fournisseur.
- Revue du 16 novembre : validation des règles et des connecteurs durcie, résidus consignés dans `TECH_DEBT.md`.
- Derrière le tunnel, Traefik remplaçait `X-Forwarded-For` par l'adresse de la passerelle Docker : tous les visiteurs partageaient une clé de limitation. Traefik fait maintenant confiance à cette seule adresse, le limiteur lit l'en-tête de droite à gauche depuis `TRUSTED_PROXIES`, le tableau de bord de Traefik n'est plus exposé, et un garde-fou rétablit ces réglages après un rechargement de Dokploy.
- API publique déplacée sur `chimeraflow-api.linguasolution.com` via le tunnel Cloudflare partagé ; ports 80 et 443 du VPS fermés.
- Dépendances du frontend corrigées (alertes Dependabot) ; README mis à jour pour la démonstration en ligne.

---

## 2026-11-17 — WhatsApp iOS, relances LLM, MCP hébergé, Redis réel

- Parseur WhatsApp : exports iOS, dates FR et EN, messages sur plusieurs lignes ; le test d'aller-retour (P3) est couvert par Hypothesis.
- Cloudflare Email Service a répondu HTTP 200 et `success: true` pour un e-mail rejeté (`permanent_bounces`) : l'envoi était journalisé comme réussi. Un rejet définitif est maintenant un échec. Le propriétaire a ensuite confirmé la réception depuis `mail.linguasolution.com`.
- Production LLM : 6 requêtes sur 10 en `502` pendant une panne passagère du proxy avec `glm-4.7-flash-bedrock` ; ajout de relances sur erreurs passagères et d'un modèle de repli. Mesure en production : 9 phrases sur 10 converties en règle valide.
- Audit d'accessibilité dans un navigateur (Edge, axe-core, 360 px, clavier) : corrections livrées ; Kiro Crew retiré du plan, le projet utilise Kiro IDE et Kiro CLI.
- Kiro n'affichait aucun serveur MCP avec la configuration locale en chemins absolus : les quatre sources sont maintenant servies en HTTP (`/mcp/<source>`, jeton Bearer, `${CHIMERAFLOW_MCP_TOKEN}`) ; PR #8 fusionnée, quatre serveurs au vert dans Kiro (constaté par le propriétaire).
- Tests : service Redis réel dans la CI (limiteur, budget LLM sous réservations concurrentes, délai d'alerte). La propriété P6 sur règles et records générés a trouvé un vrai défaut : un entier hors de la plage des flottants faisait lever `OverflowError` dans le calcul d'écart de prix (toute la règle échouait), et des flottants extrêmes donnaient un écart infini, JSON invalide. Un écart non représentable est maintenant indéfini.

**Crédits consommés :** à compléter par le propriétaire (kiro.dev/account/usage).

---

_Continue logging daily progress here._
