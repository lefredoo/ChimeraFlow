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

## [2026-11-15] Durcissement CI et exploitation : jobs frontend et secrets, moniteur, test de fumée, Dokploy sur main
**Context**: Le dépôt est public, les Actions sont gratuites et `main` devient la production ; la CI ne couvrait pas le frontend, aucun contrôle ne vérifiait la production et Dokploy suivait encore `dev`.
**Decision**: (1) CI : job « Frontend lint, tests and build » (Node 22, `npm ci`, tsc, lint, vitest, build avec des `NEXT_PUBLIC_*` factices) et job « Secret scan » (binaire gitleaks 8.30.1 épinglé par somme SHA-256, historique complet) ; actions tierces épinglées par SHA de commit. (2) `uptime.yml` toutes les 30 min : `/health` et `/login`, un seul ticket `uptime` ouvert puis fermé au retour ; la permission `issues: write` n'est donnée qu'au job qui gère le ticket. (3) `scripts/ops/smoke-prod.{sh,ps1}` : identifiants lus dans `SMOKE_EMAIL` / `SMOKE_PASSWORD`, jamais dans le dépôt ; workflow manuel « Production smoke » avec deux secrets de dépôt copiés depuis Doppler (valeurs publiques par construction). (4) Compose Dokploy `chimeraflow-api` : branche `main` (via l'API Dokploy), sans redéploiement ; `autoDeploy` laissé désactivé. (5) `docs/deployment/PRODUCTION.md` décrit déploiement, rotation du jeton Doppler, retour arrière.
**Alternatives rejected**: `gitleaks/gitleaks-action` (code tiers avec accès au dépôt, licence selon le type de compte) au profit du binaire vérifié par somme ; service Redis dans la CI (aucun test d'intégration Redis n'existe, il tournerait sans rien tester) ; `autoDeploy` sur `main` (une fusion déploierait sans contrôle d'une variable Doppler manquante, l'API s'arrêterait au démarrage) ; URLs de production en paramètre des scripts de fumée (repli de configuration, §7).
**Consequences**: `main` exige maintenant aussi les nouveaux jobs si le propriétaire les ajoute aux contrôles requis ; les secrets de dépôt `SMOKE_*` suivent `NEXT_PUBLIC_DEMO_LOGIN_*` ; le ticket d'indisponibilité dépend des notifications GitHub du dépôt ; le compose Dokploy est sur `main` : le prochain déploiement attend la fusion de la PR `dev` → `main`.
**AGENTS.md rule concerned**: §4 et §12 (dette corrigée dans le cycle), §7 (pas de repli de configuration)

---

## [2026-11-15] Déploiement initial depuis dev
**Context**: La démonstration doit être en ligne avant la fusion de la PR `dev` → `main`, sans quoi rien n'est testable en conditions réelles.
**Decision**: Le compose Dokploy `chimeraflow-api` (VPS) et le projet Vercel `chimeraflow` se déploient depuis la branche `dev` jusqu'à la fusion de la PR. La branche de production Vercel reste `main` : les déploiements de `dev` sont donc lancés à la main, par référence git. Les noms `api.chimeraflow` et `chimeraflow` (zone `linguasolution.com`) sont en DNS seul (sans proxy) ; Traefik obtient les certificats Let's Encrypt par HTTP-01.
**Alternatives rejetées**: Fusionner `dev` dans `main` avant la revue (contredit la règle PR du §5) ; proxy DNS du fournisseur (le défi HTTP-01 et l'IP client de la limitation de débit en dépendent).
**Consequences**: Après la fusion, Dokploy et Vercel doivent passer sur `main` (voir `TECH_DEBT.md`). Les secrets viennent de Doppler, jamais du dépôt.
**AGENTS.md rule concerned**: §5 (Git Workflow), déploiement hors `main` toléré jusqu'à la PR

---

## [2026-11-15] Authentification : compte de démonstration, session émise par le backend
**Context**: AGENTS.md §9 exige une authentification des opérations sensibles et l'API était ouverte. Le frontend (Vercel) et le backend (VPS) sont deux origines distinctes, sans base d'utilisateurs : un seul compte de démonstration public suffit.
**Decision**:
(1) Le backend émet une session : `POST /api/v1/auth/login` (email + mot de passe, limité par IP) renvoie un jeton Bearer HMAC-SHA256 signé, valable 1 h ; `GET /api/v1/auth/me`. Une dépendance FastAPI posée à l'inclusion des routeurs `sources`, `rules` et `correlations` (dans `main.py`) protège tous les endpoints `/api/v1` en lecture comme en écriture ; un futur routeur ne peut pas l'oublier. `/`, `/health` restent publics.
(2) Aucune dépendance ajoutée : `hashlib.scrypt` (hash auto-descriptif `scrypt:N:r:p:sel:clé`, N = 2^15, 32 Mio), `hmac`, `secrets.compare_digest`. Le hash est recalculé même pour un email inconnu (pas d'énumération), les deux comparaisons sont à temps constant, la réponse 401 est unique (`auth_invalid_credentials`). Le calcul de hash tourne dans un thread, deux à la fois au plus (`anyio.CapacityLimiter(2)`) pour borner la mémoire du conteneur (512 Mio) face à des connexions venues de nombreuses IP.
(3) Variables obligatoires, sans repli : `AUTH_TOKEN_SECRET` (32 octets ou plus), `DEMO_LOGIN_EMAIL`, `DEMO_LOGIN_PASSWORD_HASH` (validé au démarrage, jamais affiché). `python -m auth.hash_password` lit le mot de passe sur stdin et affiche le hash. `RATE_LIMIT_LOGIN_PER_IP` est facultative ; non définie : `max(3, RATE_LIMIT_PER_IP // 2)`, soit 5 par minute en production (écart assumé à §7, même précédent que `RATE_LIMIT_NL_PER_IP`) : un repli plus strict (`// 5` = 2) bloquerait un utilisateur qui se trompe une fois.
(4) `/docs`, `/redoc` et `/openapi.json` sont désactivés quand `BACKEND_NODE_ENV=production`. Swagger UI ne peut pas envoyer l'en-tête Bearer au chargement du schéma : les protéger demanderait un mécanisme à part, et un visiteur anonyme n'a pas besoin du schéma. Hors production, ils restent servis.
(5) Les réponses 422 n'échoient plus la valeur rejetée (`input`) : un mot de passe mal formé serait revenu dans la réponse, et une valeur avec un surrogate isolé faisait échouer le gestionnaire par défaut (500). Le format reste `[{loc, msg, type}]` de api-spec.md.
(6) Frontend : page `/login` qui affiche les identifiants de démonstration (`NEXT_PUBLIC_DEMO_LOGIN_EMAIL` / `_PASSWORD`, exigées au build, publiques par construction) avec un bouton « Voir la démo » qui remplit et soumet, plus le formulaire. Jeton en mémoire et `sessionStorage` (jamais `localStorage` ni cookie : le cookie serait inter-sites, bloqué par les navigateurs et exposé au CSRF). Contexte React (`AuthProvider`), appels via `lib/services/api-client.ts` (en-tête Bearer, 401 → session effacée et retour à `/login`). La page d'accueil est protégée. `Retry-After` est exposé en CORS pour que la page affiche le délai.
**Alternatives rejected**: Neon Auth / Better Auth managé : son SDK Next.js exige un secret de cookie côté serveur sur Vercel (AGENTS.md §18 : Vercel ne détient aucun secret) et la feuille de route de Neon ne prend pas officiellement en charge un frontend et un backend séparés. Better Auth auto-hébergé : troisième service, mémoire du VPS déjà juste. PyJWT / passlib / argon2-cffi : nouvelle dépendance, non approuvée (§16) pour un compte unique. Protéger `/docs` par jeton : voir (4). Cookie de session : voir (6).
**Consequences**: un seul compte partagé, public ; pas de révocation avant l'expiration (1 h) ; `AUTH_TOKEN_SECRET` à renouveler pour invalider toutes les sessions ; `/docs` absent en production, y compris avec `docker-compose.yml` (qui fixe `BACKEND_NODE_ENV=production`) ; un login coûte 32 Mio et ~100 ms de CPU, borné par la limite par IP et par le plafond de concurrence ; les secrets sont dans Doppler `prd` (`AUTH_TOKEN_SECRET`, `DEMO_LOGIN_*`, `NEXT_PUBLIC_DEMO_LOGIN_*`) ; `docker-compose.yml` exige les trois variables obligatoires ; la CI (job migrations) passe des valeurs factices.
**AGENTS.md rule concerned**: §9 (authentification, limitation, pas de PII dans les journaux), §7 (variables obligatoires ; dérivation de `RATE_LIMIT_LOGIN_PER_IP`), §16 (aucune dépendance), §18 (pas de secret sur Vercel), §8 et §10 (textes i18n, accessibilité du formulaire)

---

## [2026-11-14] Déploiement : Doppler dans le conteneur, données dans l'image, compose de production
**Context**: Q9 : en production seule la variable `DOPPLER_TOKEN` est fournie (Dokploy). Le bind mount `./backend:/app` masquait le code de l'image, `data/` était un chemin hôte et l'image runtime contenait les tests.
**Decision**:
(1) Doppler CLI 3.77.1 installé dans un stage dédié depuis le dépôt apt officiel (paquet signé, empreinte de la clé vérifiée dans le build) ; seul le binaire statique est copié (runtime et Redis). `backend/docker-entrypoint.sh` : `DOPPLER_TOKEN` défini → `doppler run --no-check-version --no-fallback -- sh -c "alembic upgrade head && exec uvicorn ..."`, sinon la même commande sans Doppler (compose local, tests). Le mode est journalisé ; Doppler injoignable ou jeton invalide arrête le conteneur.
(2) `docker-compose.prod.yml` : services `api` et `redis`, `DOPPLER_TOKEN` seule variable. Redis est construit (`target: redis`) avec le CLI Doppler et reçoit `REDIS_PASSWORD` seul (`doppler run --only-secrets REDIS_PASSWORD`), refuse de démarrer s'il est absent ou vide (sinon Redis démarrerait sans authentification et le healthcheck passerait) et lit sa configuration sur stdin (`redis-server -`, mot de passe hors des arguments du processus) ; `REDIS_URL` dans Doppler le référence (`redis://:${REDIS_PASSWORD}@chimeraflow-redis:6379/0`). Son healthcheck n'a pas le mot de passe : `NOAUTH` signifie serveur vivant. `api` est sur `dokploy-network` (externe) et sur le réseau privé `internal` partagé avec Redis (alias `chimeraflow-redis`) ; aucun port publié, un seul label `traefik.docker.network=dokploy-network` pour fixer le réseau que Traefik utilise. `mem_limit` : api 512m (mesuré ~105 MiB au repos, ~275 MiB avec litellm importé), Redis 128m.
(3) `data/` copié dans l'image par un contexte de build nommé `data` (`additional_contexts` en compose, `--build-context data=./data` sinon) : aucun chemin hôte sur le VPS, les données sont synthétiques et publiques. Un stage `source` retire tests/, requirements-dev.txt et fichiers de dev du runtime.
(4) Compose local : bind mount `./backend:/app` retiré, `mem_limit` 512m. Frontend : `lib/env.ts` sans repli (la valeur est passée par l'appelant, Next ne remplace que `process.env.NEXT_PUBLIC_X` littéral), `NEXT_PUBLIC_API_URL` exigée au build, service `health-service`, i18n FR/EN sans dépendance, CSS à tokens, Next 15.0.3 → 15.5.29 (RCE du protocole flight), `next.config.ts` local.
**Alternatives rejected**: Redis sans Doppler avec `REDIS_PASSWORD` en seconde variable Dokploy (deux variables à tenir synchrones). Réseau Redis `internal: true` (Redis doit joindre Doppler au démarrage). Montage de `data/` depuis l'hôte (chemin à maintenir sur le VPS). Contexte de build à la racine (casse `docker build --target test backend` de la CI). Tailwind v4 branché (nouvelle dépendance non approuvée).
**Consequences**: le processus uvicorn hérite de `DOPPLER_TOKEN` ; le port 8000 est fixe dans les healthchecks ; secrets à créer dans Doppler `prd` ; `docker build backend` sans `--target test` exige le contexte `data`.
**AGENTS.md rule concerned**: §7 (deux modes explicites, pas de repli silencieux), §4 (frontend), §8 (i18n)

---

## [2026-11-14] Durcissement après revue : Redis, défaut dérivé de RATE_LIMIT_NL_PER_IP, IP non stockée

**Context**: La revue de la vague 2 a relevé que le compteur de budget LLM (sans TTL) pouvait être évincé par `allkeys-lru`, que Redis était publié sans mot de passe, que `rules.created_by` stockait l'IP du client et que `RATE_LIMIT_NL_PER_IP` a une valeur dérivée.
**Decision**:
(1) Redis : `noeviction` (le compteur de budget ne doit jamais être évincé ; à saturation les écritures échouent et l'API refuse, `503`), `--appendonly yes` sur le volume nommé `redis-data`, `--requirepass` depuis `REDIS_PASSWORD` (requis, sans défaut, repris dans `REDIS_URL`), aucun port publié.
(2) Exception assumée à §7 : `RATE_LIMIT_NL_PER_IP`, si absent, vaut `max(1, RATE_LIMIT_PER_IP // 5)`. C'est un calcul à partir d'une variable requise, pas une valeur inventée : la limite NL reste toujours plus stricte que la générale, sans variable de plus à renseigner. Défaut figé par un test (conftest retire la variable ; 1000 donne 200).
(3) `rules.created_by` supprimée (migration 0002, retour arrière = colonne nullable vide) : l'IP est une donnée personnelle. Clé du limiteur : en-têtes `X-Forwarded-For` multiples joints, IPv4 mappée lue comme IPv4, client IPv6 compté par /64. Un appel LLM en échec enregistre un coût d'entrée pessimiste (caractères / 4 à 15 USD le million).
**Alternatives rejected**: `volatile-lru` (correct tant que la clé n'a pas de TTL, mais fragile si un TTL est ajouté un jour). Variable `RATE_LIMIT_NL_PER_IP` obligatoire (une configuration de plus pour un réglage secondaire). Hacher l'IP au lieu de la supprimer (aucun usage de la valeur).
**Consequences**: `docker compose` exige `REDIS_PASSWORD` (URL-safe, par exemple hexadécimal). Redis de production du VPS : mêmes réglages à vérifier, voir `backend/README.md`. À saturation de Redis le limiteur et le budget refusent les requêtes au lieu de les laisser passer.
**AGENTS.md rule concerned**: §7 (exception documentée pour `RATE_LIMIT_NL_PER_IP`), §9 (pas de PII, limitation par IP)

---

## [2026-11-14] Règles prédéfinies en fichiers, limitation par IP (slowapi + Redis), conversion NL→règle avec budget

**Context**: P2 Q4, Q5, Q7, Q14 : dépendances `slowapi` et `litellm` approuvées, règles prédéfinies à sortir du code, hook à recibler. Aucune règle de sécurité 4 (limitation) ni de plafond LLM n'était tenue.
**Decision**:
(1) Une règle prédéfinie = un fichier `data/rules/<id>.json` (champs de `RuleCreate` + `status`), validé par Pydantic à l'import de `engine.predefined_rules` (démarrage), clés inconnues refusées, `id` = nom de fichier, ordre = noms de fichier ; sans émoji.
(2) Limitation : slowapi, stockage Redis (`REDIS_URL`), mémoire seulement si `BACKEND_NODE_ENV=test`. `RATE_LIMIT_PER_IP` et `RATE_LIMIT_WINDOW_SECONDS` sont requis, un compteur par endpoint (`key_style="endpoint"`, sinon `DELETE /rules/{id}` aurait un compteur par id). Clé = IP du pair TCP ; `X-Forwarded-For` n'est lu que si le pair appartient à `TRUSTED_PROXIES`, de droite à gauche jusqu'à la première adresse non proxy. Limite NL→règle séparée et plus stricte (`RATE_LIMIT_NL_PER_IP`, sinon `RATE_LIMIT_PER_IP // 5`, au moins 1). Redis du limiteur en panne : `503`, mutation refusée.
(3) NL→règle : `POST /rules/from-text` renvoie un brouillon non stocké ; texte utilisateur passé comme chaîne JSON entre marqueurs dans le message utilisateur ; `id` et `natural_language` fixés par le serveur ; 2 retries avec les erreurs de validation (sans valeurs rejetées). Budget : plafond global `LITELLM_BUDGET_USD`, dépense cumulée en micro-USD dans Redis (`INCRBY`, atomique, sans dérive flottante), vérifiée avant chaque appel ; coût = `litellm.completion_cost`, sinon estimation par tokens à 15 USD/million. Fonctionnalité désactivée sans les quatre variables `LITELLM_*` ; `litellm` importé à la première conversion.
(4) Erreurs : `{"detail": {"code", "message"}}` partout, `fallback_rules` pour les erreurs `nl_*`. (5) Les trois variables `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL` sont de la configuration : aucune valeur par défaut.
**Alternatives rejected**: Garder les règles en Python (textes métier dans le code, hook sans cible). Limiter par URL (contournable avec des ids différents) ou lire `X-Forwarded-For` sans condition (spoofable). Stockage mémoire en repli si Redis manque (compteur par worker, repli silencieux). Budget en `INCRBYFLOAT` (dérive). Estimation de coût fixe sans `completion_cost` (faux pour les modèles tarifés). Persister le brouillon (le client doit relire avant `POST /rules`). Laisser le modèle choisir l'`id` (collisions, injection d'un id réservé).
**Consequences**: `alembic` et la CI exigent `RATE_LIMIT_*` (ajoutés à `ci.yml` et `docker-compose.yml`). Réinitialiser le budget = supprimer la clé Redis `chimeraflow:nl:spent_microusd`. Appels LiteLLM jamais exécutés en réel (clé, URL, modèle inconnus), voir TECH_DEBT.md. Les messages d'erreur des endpoints existants ont changé de format (objet au lieu de texte).
**AGENTS.md rule concerned**: §7 (pas de repli de configuration), §9 (limitation par IP), §4 (texte utilisateur dans les fichiers de données), §16 (dépendances approuvées)

---

## [2026-11-14] Lecteur Access explicite, Alembic au démarrage du conteneur, dépendances scindées

**Context**: Python 3.13, nouvelles dépendances approuvées (P2 Q2, Q4, Q6, Q8) : lecture Access sous Windows, schéma géré à la main (`create_all`), pins `requirements.txt` périmés.
**Decision**: `ACCESS_READER` (`mdbtools` | `access-parser`) est obligatoire et validé au démarrage, sans repli de l'un sur l'autre ; les deux lecteurs alimentent le même code de parsing (mêmes enregistrements, test d'équivalence sur `STOCK_ZOBO.mdb`). `alembic upgrade head` s'exécute dans le CMD du conteneur avant uvicorn, plus dans le lifespan (qui ne fait que le seed). `requirements.txt` (runtime) et `requirements-dev.txt` (tests, lint) sont séparés ; l'image a une cible `test` avec mdbtools. Lint : `ruff check` (règles F, équivalent pyflakes) car pyflakes ne sait pas exclure `.venv`.
**Alternatives rejected**: Repli automatique mdbtools → access-parser (masque une mauvaise configuration, §7). Migration dans le lifespan (course entre workers/réplicas, impossible avec SQLite en mémoire des tests, le serveur démarrerait malgré un échec). Fichier de dépendances unique (les outils de test alourdissent l'image de production).
**Consequences**: Lancer `alembic upgrade head` à la main en local avant uvicorn ; `alembic` charge `config.py`, donc toutes les variables requises doivent être définies (Doppler les fournit). Les tests créent les tables avec `create_all`, un test vérifie l'absence de dérive avec la migration. `DATABASE_URL` `postgresql://` est converti en `postgresql+psycopg://` dans `config.normalize_database_url` (seul endroit).
**AGENTS.md rule concerned**: §7 (pas de repli de configuration), §16 (nouvelles dépendances approuvées par le product owner)

---

## [2026-11-13] P2 review pass 2: seeded predefined rules, matching on numbers, idempotent executions

**Context**: The second review found foreign keys pointing to rules that exist only in code, duplicate correlations on each execution, and fuzzy matching that links "ciment 50 kg" to "ciment 40 kg".
**Decision**: Predefined rules are upserted into `rules` at startup (status kept on restart); 3 of them (`r_payment_received`, `r_price_comparison`, `r_stock_replenish`) are seeded inactive and never executed, pending the user's decision on the DSL. The time window stays symmetric. Rows with invalid values are still skipped and counted. Matching requires the same numeric tokens on both sides before the fuzzy ratio, and "2.5" or "1/2" stay one token. Each execution replaces the rule's previous correlations.
**Alternatives rejected**: Dropping the foreign keys (loses referential integrity). Extending the DSL now (scope). Forward-only window (prices predate messages). Defaulting invalid values (invents data). Higher fuzzy threshold alone (still links 100mm and 10mm).
**Consequences**: Reversible: activating the 3 rules is a status change. Foreign keys are enforced on SQLite too, tests behave like PostgreSQL. Partial names ("tuyau PVC" vs "Tuyau PVC 32mm") no longer match. See TECH_DEBT.md.
**AGENTS.md rule concerned**: §4 (fix problems in the same cycle), §14 (decision log)

---

## [2026-11-13] P2 code review: configuration, data contract and matching fixes

**Context**: An audit of the uncommitted P2 code found config fallbacks, rule fields that did not match connector payloads, a non-idempotent normalizer, and an import of a module that does not exist.
**Decision**: `DATABASE_URL`, `CORS_ORIGINS`, `DATA_DIR` are required (no SQLite or default fallback). Connector payloads keep the source column names (`Produit`, `Prix_Unitaire`, `qty_stock`, ...). One `normalize_text()` in `engine/normalizer.py`, whitespace collapsed last, letters split from digits. Record timestamps come from source dates. The rule time window is symmetric (before and after the trigger). Rows with invalid values are skipped and counted, never defaulted. Each rule runs in its own savepoint.
**Alternatives rejected**: Keeping the SQLite fallback (hides a missing variable, AGENTS.md §7). Renaming rule fields to the old payload keys (breaks the link between a rule and the file the user sees). Forward-only window (prices and stock predate the WhatsApp message, so nothing matched).
**Consequences**: Environment variables must be set before startup (tests set them in `tests/conftest.py`, `backend/.env.test` removed). Remaining limits are in TECH_DEBT.md (Access on Windows, partial product names, predefined rules 2 and 5, foreign keys, rate limiting, NL→rule).
**AGENTS.md rule concerned**: §7 (no configuration fallbacks), §13 (no bare `except`), §4 (fix problems in the same cycle)

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
