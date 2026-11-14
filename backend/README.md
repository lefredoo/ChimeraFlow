# ChimeraFlow Backend

FastAPI backend for the correlation engine.

## Architecture

```
backend/
├── api/                    # REST API endpoints
│   ├── sources.py          # GET /sources (P1)
│   ├── rules.py            # POST /rules, POST /rules/from-text, GET /rules
│   ├── correlations.py     # POST /correlations/execute, GET /correlations
│   ├── errors.py           # Codes d'erreur stables + corps d'erreur
│   ├── rate_limit.py       # Limitation par IP (slowapi + Redis), IP client / proxys de confiance
│   └── nl_dependencies.py  # Dépendances FastAPI de la conversion NL→règle
├── engine/                 # Rule engine (P2)
│   ├── interpreter.py      # Rule interpreter (trigger, joins, where, emit)
│   ├── normalizer.py       # Normalization (single implementation) + fuzzy match + synonyms
│   ├── rule_files.py       # Lecture et validation de data/rules/*.json (module pur)
│   ├── predefined_rules.py # Charge les règles prédéfinies au démarrage (échec immédiat si invalide)
│   ├── validate_rules.py   # CLI : python -m engine.validate_rules [dossier]
│   ├── nl_to_rule.py       # Conversion NL→règle (prompt structuré, retries, budget)
│   ├── nl_budget.py        # Compteur de dépense LLM (Redis)
│   └── llm_client.py       # Frontière LiteLLM (import à la demande)
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
│   ├── test_rule_files.py  # Chargement de data/rules/*.json, CLI de validation
│   ├── test_rate_limit.py  # 429, Retry-After, IP client, variables requises
│   ├── test_nl_to_rule.py  # Conversion NL→règle (LiteLLM mocké) : retries, budget, désactivation, injection
│   ├── test_api_errors.py  # Codes d'erreur stables
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
| `REDIS_URL` | Redis connection: compteurs de limitation et dépense LLM (not required when `BACKEND_NODE_ENV=test`) |
| `ACCESS_READER` | `mdbtools` (Docker, production) or `access-parser` (pure Python, local Windows). Any other value stops the startup |
| `RATE_LIMIT_PER_IP` | Requêtes de mutation autorisées par IP et par fenêtre (entier ≥ 1) |
| `RATE_LIMIT_WINDOW_SECONDS` | Durée de la fenêtre de limitation, en secondes (entier ≥ 1) |

**Optional** (the related behavior is disabled or left to the library default when unset)

| Variable | Purpose |
|----------|---------|
| `BACKEND_NODE_ENV` | `development`, `production` or `test` |
| `BACKEND_PORT` | Port used by `python main.py` (uvicorn default when unset) |
| `BACKEND_LOG_LEVEL` | Logging level |
| `RATE_LIMIT_NL_PER_IP` | Limite de `POST /rules/from-text` par IP et par fenêtre. Non définie : `RATE_LIMIT_PER_IP // 5` (au moins 1) |
| `TRUSTED_PROXIES` | Adresses IP ou réseaux CIDR (séparés par des virgules) des proxys dont l'en-tête `X-Forwarded-For` est cru (Traefik). Non définie : l'IP du pair TCP sert de clé |
| `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL`, `LITELLM_BUDGET_USD` | Conversion NL→règle. **Les quatre** doivent être définies, sinon la fonctionnalité est désactivée (`503 nl_feature_disabled`) |

`LITELLM_MODEL` est une chaîne de modèle LiteLLM. Pour un proxy LiteLLM, utiliser
`openai/<alias du modèle sur le proxy>` et `LITELLM_BASE_URL` = URL du proxy.
`LITELLM_BUDGET_USD` est le plafond **global** de dépense (USD), suivi dans Redis. Il doit être un nombre
fini strictement positif (`nan`, `inf`, `0` et les valeurs négatives arrêtent le démarrage).

`docker-compose.yml` exige en plus `REDIS_PASSWORD` (mot de passe de Redis, sans défaut). Il doit pouvoir
figurer dans une URL, par exemple `openssl rand -hex 24` ; le compose le reprend dans `REDIS_URL`
(`redis://:<mot de passe>@redis:6379/0`).

### Redis en production

Redis porte le budget LLM (clé `chimeraflow:nl:spent_microusd`, **sans expiration**) et les compteurs du
limiteur. Pour le Redis déjà exploité sur le VPS, vérifier :

| Réglage | Valeur | Raison |
|---------|--------|--------|
| `maxmemory-policy` | `noeviction` (ou `volatile-lru` tant que la clé du budget n'a pas de TTL) | Avec `allkeys-lru`, la clé du budget peut être évincée : le budget serait remis à zéro. À saturation, `noeviction` fait échouer les écritures : l'API refuse (`503`) au lieu de laisser passer |
| Persistance | `appendonly yes`, sur un volume | Sans elle, un redémarrage remet budget et compteurs à zéro |
| Authentification | `requirepass` (ou ACL) ; mot de passe dans `REDIS_URL` | Quiconque atteint Redis peut remettre le budget à zéro |
| Exposition | aucun port publié sur l'hôte ; réseau Docker privé | Redis n'est jamais joignable depuis Internet |

Contrôle : `redis-cli CONFIG GET maxmemory-policy`, `CONFIG GET appendonly`, `CONFIG GET requirepass`.
Le `docker-compose.yml` du dépôt applique ces réglages (volume `redis-data`, aucun port publié).

`alembic` charge `config.py` : les variables requises (dont `RATE_LIMIT_*`)
doivent aussi être définies pour les migrations.

Example (PowerShell):

```powershell
$env:DATABASE_URL = "postgresql://user:pass@host/dbname"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:DATA_DIR = "../data"
$env:ACCESS_READER = "access-parser"
$env:RATE_LIMIT_PER_IP = "10"
$env:RATE_LIMIT_WINDOW_SECONDS = "60"
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
POST /api/v1/rules/from-text      # Conversion NL→règle : renvoie un brouillon, ne stocke rien (limité par IP, plus strict)
POST /api/v1/rules                # Create new rule (validated; 409 if the id exists or is predefined) (limité par IP)
GET  /api/v1/rules                # List all rules (filter by status)
GET  /api/v1/rules/{id}           # Get specific rule
DELETE /api/v1/rules/{id}         # Delete rule and its correlations (limité par IP)
```

### Correlations (P2)

```
POST /api/v1/correlations/execute # Execute active rules (query: rule_ids, max 20) (limité par IP)
GET  /api/v1/correlations         # List correlations (filter by rule_id, severity; limit 1 to 1000)
```

### Conversion NL→règle (`POST /api/v1/rules/from-text`)

Corps (le texte n'est jamais dans l'URL) :

```json
{"text": "Alerte-moi quand le stock de ciment est inférieur à 10.", "language": "fr"}
```

`text` : 20 à 1000 caractères (espaces de début et de fin retirés). `language` : `fr` ou `en`,
langue du gabarit d'alerte généré.

Réponse `200` : `{"rule": {...}, "retries": 0}`. Le brouillon est valide selon `RuleCreate` mais **n'est pas
stocké** : le client l'envoie ensuite à `POST /api/v1/rules`. Son `id` est généré (`r_nl_…`) et son
`natural_language` est le texte de l'utilisateur, pas une reformulation du modèle.

Fonctionnement :

- Le prompt sépare les instructions (message système) du texte utilisateur, transmis comme une chaîne JSON
  entre les marqueurs `<<<USER_DATA` et `USER_DATA>>>` du message utilisateur. Toute suite de 3 `<` ou plus et de 3 `>` ou
  plus dans le texte est ramenée à 2 caractères.
- La réponse du modèle doit être un objet JSON (une clôture markdown est tolérée). Elle est validée avec
  `RuleCreate` ; seules les clés `trigger`, `joins`, `window_seconds`, `emit` sont admises. Rien n'est exécuté.
- En cas de réponse invalide, le modèle reçoit l'erreur de validation (chemins et messages, sans les valeurs
  rejetées) et réessaie, **2 fois au plus** (3 appels maximum).
- Budget : avant chaque appel, la dépense cumulée (Redis, clé `chimeraflow:nl:spent_microusd`, en micro-USD)
  est comparée à `LITELLM_BUDGET_USD`. Le coût d'un appel vient de `litellm.completion_cost` ; si LiteLLM ne
  sait pas chiffrer le modèle, il est estimé à partir des tokens (15 USD par million, volontairement pénalisant).
  Réinitialiser le budget : supprimer la clé Redis. Si Redis ne répond pas, le budget ne peut pas être vérifié
  et la requête est refusée.
  Un appel en échec (délai, erreur du fournisseur, quelle qu'en soit la classe) peut avoir été facturé :
  un coût d'entrée pessimiste (caractères / 4, au même prix) est enregistré.
- Délai : 20 s par appel au fournisseur.
- Les journaux ne contiennent ni le texte, ni la réponse du modèle, ni la clé d'API.

### Format des erreurs

Toute erreur applicative a le corps `{"detail": {"code": "<code_stable>", "message": "<message court en anglais>"}}`.
Le client traduit le `code` ; le `message` est une aide pour le développeur et ne s'affiche pas. Les erreurs
de validation de requête (`422` de FastAPI) gardent le format liste de FastAPI.

| Code | HTTP | Cas |
|------|------|-----|
| `rule_not_found`, `source_not_found` | 404 | Ressource inconnue |
| `rule_already_exists` | 409 | Identifiant déjà pris ou réservé (règle prédéfinie) |
| `invalid_status`, `invalid_severity` | 400 | Filtre invalide |
| `source_fetch_failed` | 500 | Lecture de la source impossible |
| `rate_limit_exceeded` | 429 | Limite par IP dépassée (en-tête `Retry-After` en secondes) |
| `rate_limit_unavailable` | 503 | Redis du limiteur injoignable : la mutation est refusée |
| `nl_feature_disabled` | 503 | Variables `LITELLM_*` incomplètes |
| `nl_budget_exceeded` | 503 | Budget LLM épuisé |
| `nl_budget_unavailable` | 503 | Compteur de dépense illisible |
| `nl_provider_error` | 502 | Le fournisseur LLM a échoué (réseau, délai, HTTP) |
| `nl_conversion_failed` | 422 | Aucune règle valide après 2 retries |

Les erreurs `nl_*` ajoutent `fallback_rules` à `detail` : les règles prédéfinies (même format que
`GET /rules/predefined`), à proposer à la place de la conversion.

### Limitation par IP

Les endpoints de mutation (`POST /rules`, `DELETE /rules/{id}`, `POST /correlations/execute`,
`POST /rules/from-text`) sont limités par IP avec slowapi. Chaque endpoint a son compteur (Redis, partagé
entre les workers) : `RATE_LIMIT_PER_IP` requêtes par fenêtre de `RATE_LIMIT_WINDOW_SECONDS` secondes, et
`RATE_LIMIT_NL_PER_IP` pour la conversion NL→règle. Les requêtes refusées par la validation (`422`) ne sont pas
comptées : elles n'atteignent pas le endpoint. Les lectures ne sont pas limitées.

IP du client : l'adresse du pair TCP. Derrière Traefik, définir `TRUSTED_PROXIES` : `X-Forwarded-For` n'est lu
que si le pair en fait partie, de droite à gauche, jusqu'à la première adresse qui n'est pas un proxy de
confiance (plusieurs lignes d'en-tête sont lues comme une seule liste). Une adresse IPv4 mappée en IPv6
(`::ffff:a.b.c.d`) compte comme l'IPv4, et un client IPv6 est compté par préfixe `/64`. L'adresse n'est
jamais stockée en base. Une valeur écrite par le client à gauche de l'adresse ajoutée par le proxy est ignorée. Le stockage
en mémoire n'est utilisé que si `BACKEND_NODE_ENV=test`.

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

### Règles prédéfinies (`data/rules/*.json`)

Une règle = un fichier `<DATA_DIR>/rules/<id>.json` : les champs de `RuleCreate` plus `status`
(`active` ou `inactive`, statut du seed initial). `engine/predefined_rules.py` les charge **au démarrage** avec
Pydantic : une clé inconnue, un `id` différent du nom de fichier, un statut absent ou une règle invalide
arrêtent l'application. L'ordre est celui des noms de fichier. Les textes `natural_language` et
`emit.template` sont des données métier (sans émoji : la sévérité est un champ). Vérifier les fichiers
sans lancer l'application :

```bash
python -m engine.validate_rules            # <DATA_DIR>/rules
python -m engine.validate_rules ../data/rules
```

Le hook `.kiro/hooks/rule-validate.json` se déclenche à l'enregistrement d'un fichier de `data/rules/`.

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
`CORS_ORIGINS`, `RATE_LIMIT_PER_IP`, `RATE_LIMIT_WINDOW_SECONDS`), so no `.env` file is needed.
`BACKEND_NODE_ENV=test` est aussi ce qui sélectionne le stockage mémoire du limiteur (choix explicite, pas un repli).

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
- Implemented: **rate limiting** per IP on every mutation endpoint (slowapi + Redis), 429 with `Retry-After`
- Implemented: **LLM budget cap** (`LITELLM_BUDGET_USD`, spend counter in Redis, refusal once exceeded)
- Implemented: user text separated from instructions in the LLM prompt, model answer validated with `RuleCreate`
- Implemented: no IP address, user text or API key in the logs of the new code (slowapi's own warning, which names the IP, is silenced)
- Not implemented yet: **sanitization** of source text before display (frontend work)

## Development

### Adding a new connector

1. Create `backend/mcp_servers/my_connector.py`
2. Extend `BaseConnector`
3. Implement `fetch_records()` and `_perform_health_check()`
4. Return `UnifiedRecord` objects with the source's original column names in the payload
5. Add tests in `tests/test_connectors.py`

### Adding a new rule

Via l'API (`POST /api/v1/rules`, éventuellement à partir d'un brouillon de `POST /api/v1/rules/from-text`), ou
pour une règle prédéfinie, en ajoutant `data/rules/r_my_rule.json` (voir le format ci-dessus) puis
`python -m engine.validate_rules`. Le seed l'insère au prochain démarrage.

---

**Phase**: P2 (Moteur de règles) — in progress (interpreter, normalizer, rules and correlations API, rate limiting and NL→rule done; DSL extensions pending)
