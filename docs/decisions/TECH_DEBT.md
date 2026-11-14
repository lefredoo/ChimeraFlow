# Technical Debt

Issues identified but not resolved in the current cycle.
Required by AGENTS.md §15.

---

## Format

[YYYY-MM-DD] Problem description | Estimated impact (low/med/high) | Concerned file(s)

---

## Current Debt

- [2026-11-14] Next.js 15.5.29 : `npm audit --omit=dev` signale encore 2 avis (postcss embarqué par next, XSS/lecture de source map, correctif seulement dans Next 16, changement majeur) ; postcss ne traite ici que le CSS du dépôt au build | Low | frontend/package.json
- [2026-11-14] Tailwind v4 déclaré dans package.json mais non branché (ni `@tailwindcss/postcss` ni `postcss.config`) : le CSS du frontend est du CSS simple à tokens ; brancher Tailwind demande une dépendance à approuver | Low | frontend/package.json, frontend/app/globals.css
- [2026-11-14] `next lint` est déprécié (retiré dans Next 16) : migrer vers l'ESLint CLI (`npx @next/codemod@canary next-lint-to-eslint-cli .`) | Low | frontend/package.json, frontend/.eslintrc.json
- [2026-11-14] Le processus uvicorn hérite de `DOPPLER_TOKEN` (`doppler run` transmet l'environnement) ; un jeton de service en lecture seule limite l'exposition | Low | backend/docker-entrypoint.sh
- [2026-11-14] HEALTHCHECK de l'image et des compose en dur sur le port 8000 : `BACKEND_PORT` dans Doppler doit rester absent ou égal à 8000 | Low | backend/Dockerfile, docker-compose.prod.yml
- [2026-11-14] Image `redis:7-alpine` non figée par digest (tag mobile) et Doppler CLI épinglé à 3.77.1 sans mise à jour automatique | Low | backend/Dockerfile
- [2026-11-14] Documentation à mettre à jour (hors périmètre de cette tâche, édition en cours par un autre agent) : le build runtime exige `--build-context data=./data` hors compose, `docker-compose.prod.yml` et le démarrage Doppler ne sont décrits ni dans README.md, backend/README.md ni docs/deployment | Med | README.md, backend/README.md, docs/deployment/P0-setup.md
- [2026-11-14] Compose de production non éprouvé sur le VPS (Dokploy, Traefik, Doppler réel) : seuls des essais locaux avec un faux serveur Doppler ont été faits | Med | docker-compose.prod.yml
- [2026-11-14] Pas de job frontend dans la CI (tsc, lint, vitest, build, audit) : les contrôles frontend ne tournent qu'en local | Med | .github/workflows/ci.yml
- [2026-11-14] `@import` Google Fonts dans globals.css : requête vers un tiers (confidentialité, CSP) ; migrer vers `next/font` (auto-hébergement des polices IBM Plex) | Low | frontend/app/globals.css
- [2026-11-14] `npm audit` hors production : vitest 1.x (esbuild, tinypool) et minimatch (typescript-eslint) signalés, correctif de vitest seulement en 4.x (majeur) ; outils de dev uniquement, absents du build déployé | Low | frontend/package.json
- [2026-11-14] CI GitHub Actions bloquée : jobs non démarrés pour cause de facturation du compte (paiement échoué ou plafond de dépenses), run 43569157569 | High | .github/workflows/ci.yml
- [2026-11-14] `_record_spend` : un INCRBY en échec est seulement journalisé ; la dépense n'est pas comptée (sécurité assurée aujourd'hui par le 503 du limiteur) | Low | backend/engine/nl_to_rule.py
- [2026-11-14] Caractères non URL-safe de REDIS_PASSWORD non vérifiés au démarrage | Low | docker-compose.yml, backend/config.py
- [2026-11-14] Pas de service Redis dans la CI (chemins Redis du limiteur et du budget non testés automatiquement) | Med | .github/workflows/ci.yml
- [2026-11-14] Budget LLM : la dépense est enregistrée après l'appel ; réserver le coût estimé par `INCRBY` avant l'appel puis corriger après la réponse supprimerait le dépassement dû aux appels concurrents | Med | backend/engine/nl_to_rule.py, backend/engine/nl_budget.py
- [2026-11-14] Les `template` générés par le modèle ne sont pas limités à une liste de colonnes autorisées : `{momo.phone}` ou `{momo.customer_name}` exposent des données personnelles dans les corrélations | Med | backend/engine/nl_to_rule.py, backend/schemas/rule.py
- [2026-11-14] Schéma `RuleCreate` sans borne sur la liste `where` ni sur la longueur des champs (`field`, `value`, `template`) : un brouillon NL peut être démesuré | Med | backend/schemas/rule.py
- [2026-11-14] Des tests manipulent les internes du limiteur (`limiter.limiter.hit`, `limiter.reset`) au lieu de ne mocker que la frontière Redis | Low | backend/tests/test_rate_limit.py, backend/tests/conftest.py
- [2026-11-14] Boucles `for` dans le corps de tests (règle « pas de logique dans les tests ») | Low | backend/tests/test_rate_limit.py
- [2026-11-14] La conversion NL→règle n'a jamais appelé le vrai proxy LiteLLM (clé, URL et modèle inconnus) : `response_format` json_object, `drop_params`, la forme du nom de modèle et `completion_cost` sont non vérifiés en réel | Med | backend/engine/llm_client.py
- [2026-11-14] RedisSpendStore et le limiteur ne sont testés qu'avec un faux client Redis et le stockage mémoire (vérifiés une fois à la main sur Redis local) ; la CI n'a pas de service Redis | Med | backend/tests/test_nl_to_rule.py, backend/tests/test_rate_limit.py, .github/workflows/ci.yml
- [2026-11-14] Plafond de budget vérifié avant chaque appel, coût ajouté après : des appels concurrents peuvent dépasser le plafond d'environ (appels en vol × coût d'un appel), borné par la limite par IP | Low | backend/engine/nl_to_rule.py
- [2026-11-14] Prix de repli (15 USD / million de tokens) quand LiteLLM ne sait pas chiffrer le modèle : constante en code, non configurable | Low | backend/engine/llm_client.py
- [2026-11-14] Un brouillon NL est validé par `RuleCreate` mais ses `field` (`on.field`, `where.field`, placeholders) ne sont pas confrontés aux colonnes réelles des sources : une colonne inventée ne correspond jamais | Med | backend/engine/nl_to_rule.py, backend/schemas/rule.py
- [2026-11-14] Le `template` généré par le modèle dérive d'un texte non fiable : le frontend doit l'échapper à l'affichage (comme les textes de sources) | Med | frontend
- [2026-11-14] `limits.errors.StorageError` importé directement depuis `limits`, dépendance transitive de slowapi non épinglée dans requirements.txt | Low | backend/api/rate_limit.py, backend/requirements.txt
- [2026-11-14] access-parser : une colonne Currency avec propriété Format renvoie une chaîne formatée, prix_achat devient None | Low | backend/mcp_servers/access_connector.py
- [2026-11-14] Équivalence des lecteurs Access vérifiée seulement là où mdbtools est installé (Docker) : à exécuter en CI | Med | backend/tests/test_access_readers.py
- [2026-11-14] Boucle for/if dans un test (règle « pas de logique dans les tests ») | Low | backend/tests/test_access_readers.py
- [2026-11-14] `access-parser` reader has no 5 s timeout (in-process, unlike `mdb-export`) | Low | backend/mcp_servers/access_connector.py
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

### [2026-11-14] Entity matching is whole-string, so partial product names do not match | Medium | backend/engine/interpreter.py, backend/engine/normalizer.py

**Problem**: `EntityNormalizer.match` compares the full normalized strings with a Levenshtein similarity (`rapidfuzz`, threshold 0.85), after requiring the same numbers on both sides ("ciment 50 kg" never matches "ciment 40 kg"). "perceuse 500W" vs "Perceuse électrique 500W" scores 0.56 (0.72 with the former `difflib` ratio) and "tuyau PVC" vs "Tuyau PVC Ø 32mm (barre 6m)" is rejected by the numeric guard, so only products written in full (the "ciment 50 kg" scenario) correlate. On the real data files, `r_high_value_order` finds nothing.

**Impact**: Medium - the 4-variants demo works, other products do not.

**Solution**: Decide the matching strategy: token containment, `rapidfuzz` token-set ratio (the library is now installed), or richer WhatsApp extraction.

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

### [2026-11-13] No containerization for MCP servers yet | Medium | backend/

**Problem**: P1 focused on connector logic. Docker Compose exists but MCP server container not yet configured.

**Impact**: Medium - deployment to VPS Hetzner will need container setup.

**Solution**: P3 task (Docker integration).

---

_Add new entries at the top of this file (reverse chronological order)._
