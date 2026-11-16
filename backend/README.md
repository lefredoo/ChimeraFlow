# Backend ChimeraFlow

API FastAPI du moteur de corrélation.

## Architecture

```
backend/
├── api/                    # endpoints REST
│   ├── sources.py          # GET /api/v1/sources (P1)
│   ├── rules.py            # POST /rules, POST /rules/from-text, GET /rules
│   ├── correlations.py     # POST /correlations/execute, GET /correlations (since)
│   ├── correlation_stream.py # GET /correlations/stream (SSE)
│   ├── normalize.py        # POST /normalize (bac à sable de normalisation)
│   ├── demo.py             # POST /demo/reset
│   ├── errors.py           # codes d'erreur stables et corps d'erreur
│   ├── rate_limit.py       # limitation par IP (slowapi + Redis), IP client et proxys de confiance
│   └── nl_dependencies.py  # dépendances FastAPI de la conversion NL→règle
├── engine/                 # moteur de règles (P2)
│   ├── interpreter.py      # interpréteur (déclencheur, joins, where, emit)
│   ├── normalizer.py       # normalisation (implémentation unique), similarité floue, synonymes
│   ├── rule_files.py       # lecture et validation de data/rules/*.json (module pur)
│   ├── predefined_rules.py # charge les règles prédéfinies au démarrage (échec immédiat si invalide)
│   ├── validate_rules.py   # CLI : python -m engine.validate_rules [dossier]
│   ├── nl_to_rule.py       # conversion NL→règle (prompt structuré, relances, budget)
│   ├── alerts.py           # e-mail récapitulatif des nouvelles corrélations (Cloudflare Email Service)
│   ├── nl_budget.py        # compteur de dépense LLM (Redis)
│   └── llm_client.py       # frontière LiteLLM (import à la demande)
├── mcp_servers/            # connecteurs de sources (P1)
│   ├── base.py             # BaseConnector et schéma UnifiedRecord
│   ├── excel_connector.py  # lecture Excel (pandas + openpyxl)
│   ├── access_connector.py # lecture Access (CLI mdbtools ou access-parser, selon ACCESS_READER)
│   ├── whatsapp_connector.py # parseur WhatsApp (expression régulière, format Android)
│   ├── momo_connector.py   # lecture du CSV Mobile Money
│   ├── mcp_app.py          # serveur MCP stdio d'une source (outils fetch_records, health_check)
│   ├── mcp_settings.py     # réglages des serveurs MCP (DATA_DIR, ACCESS_READER), sans config.py
│   └── kiro-mcp.json       # modèle de .kiro/settings/mcp.json
├── mcp_main.py             # lanceur : python mcp_main.py --source excel|access|whatsapp|momo
├── migrations/             # migrations Alembic (env.py lit DATABASE_URL)
├── models/                 # modèles SQLAlchemy (P2)
│   ├── base.py             # configuration de la base (clés étrangères activées sur SQLite)
│   ├── rule.py             # Rule, RuleExecution, Correlation
│   └── seed.py             # seed idempotent des règles prédéfinies au démarrage
├── schemas/                # validation Pydantic (P2)
│   ├── rule.py             # RuleCreate, RuleResponse, etc.
│   ├── sources.py          # colonnes exposées par chaque source (liste blanche du DSL)
│   └── normalize.py        # schémas du bac à sable
├── tests/                  # tests (voir tests/README.md)
│   ├── conftest.py         # variables d'environnement de test, profils Hypothesis, fixture api_client
│   ├── factories.py        # records unifiés en mémoire pour les tests du moteur et de l'API
│   ├── test_api_correlations.py # seed, exécution, clés étrangères, idempotence
│   ├── test_connectors.py  # tests de contrat (R1 à R4)
│   ├── test_connector_payloads.py # noms de champs, entités, erreurs de parsing
│   ├── test_access_readers.py # mdbtools et access-parser produisent les mêmes records
│   ├── test_mcp_servers.py # serveurs MCP : outils, limite, ressource, configuration, lancement stdio
│   ├── test_migrations.py  # alembic upgrade head / downgrade base, pas de dérive avec les modèles
│   ├── test_properties.py  # tests basés sur les propriétés (Hypothesis)
│   ├── test_normalizer.py  # variantes de normalisation, idempotence, nombres
│   ├── test_interpreter.py # exécution des règles, provenance, choix du meilleur candidat, rendu des templates
│   ├── test_interpreter_properties.py # P1, P4, P5 sur des entrées générées (Hypothesis)
│   ├── test_api_features.py # explication, `since`, flux, e-mail, bac à sable, réinitialisation
│   ├── test_alerts.py      # e-mail récapitulatif (transport HTTP simulé)
│   ├── test_scenario_data.py # chaque règle prédéfinie trouve une corrélation sur les données livrées
│   ├── test_connector_errors.py # erreurs de format, compteur d'erreurs par lecture
│   ├── test_schemas.py     # validation du schéma de règle
│   ├── test_rule_files.py  # chargement de data/rules/*.json, CLI de validation
│   ├── test_rate_limit.py  # 429, Retry-After, IP client, variables requises
│   ├── test_nl_to_rule.py  # conversion NL→règle (LiteLLM simulé) : relances, budget, désactivation, injection
│   ├── test_api_errors.py  # codes d'erreur stables
│   └── test_health.py      # tests de fumée de l'API
├── config.py               # configuration par variables d'environnement
├── main.py                 # application FastAPI
├── alembic.ini             # configuration Alembic
├── Dockerfile              # cibles base, test et runtime
├── spike_access.py         # script de test de lecture d'un .mdb
├── requirements.txt        # dépendances d'exécution (Python 3.13)
└── requirements-dev.txt    # outils de test et de lint
```

## Installation

### 1. Installer les dépendances

Environnement virtuel Python 3.13 avec [uv](https://docs.astral.sh/uv/) (`.venv` ignoré par Git) :

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

Sous Linux ou macOS : `.venv/bin/python` à la place de `.venv\Scripts\python.exe`.

### 2. Configurer l'environnement

Le backend lit uniquement des variables d'environnement, sans chargeur de `.env`. En production,
elles viennent de Doppler. En local, les exporter dans le shell. Une variable requise absente
arrête l'application au démarrage, c'est voulu (AGENTS.md §7).

**Requises**

| Variable | Rôle |
|----------|------|
| `DATABASE_URL` | chaîne de connexion SQLAlchemy (PostgreSQL sur Neon en production) |
| `CORS_ORIGINS` | liste d'origines autorisées, séparées par des virgules |
| `DATA_DIR` | dossier des fichiers de données synthétiques |
| `REDIS_URL` | connexion Redis : compteurs de limitation et de dépense LLM (non requise quand `BACKEND_NODE_ENV=test`) |
| `ACCESS_READER` | `mdbtools` (Docker, production) ou `access-parser` (Python pur, Windows local). Toute autre valeur arrête le démarrage |
| `RATE_LIMIT_PER_IP` | requêtes de mutation autorisées par IP et par fenêtre (entier ≥ 1) |
| `RATE_LIMIT_WINDOW_SECONDS` | durée de la fenêtre de limitation, en secondes (entier ≥ 1) |
| `AUTH_TOKEN_SECRET` | secret de signature des jetons d'accès, 32 octets ou plus (par exemple 48 octets aléatoires en hexadécimal). Le renouveler invalide toutes les sessions |
| `DEMO_LOGIN_EMAIL` | email du compte de démonstration (comparé sans casse ni espaces de bord) |
| `DEMO_LOGIN_PASSWORD_HASH` | hash scrypt du mot de passe du compte, produit par `python -m auth.hash_password` (voir Authentification). Un hash mal formé arrête le démarrage, sans être affiché |

**Facultatives** (le comportement associé est désactivé, ou laissé au défaut de la bibliothèque, quand elles ne sont pas définies)

| Variable | Rôle |
|----------|------|
| `BACKEND_NODE_ENV` | `development`, `production` ou `test` |
| `BACKEND_PORT` | port utilisé par `python main.py` (défaut d'uvicorn si absent) |
| `BACKEND_LOG_LEVEL` | niveau de journalisation |
| `RATE_LIMIT_NL_PER_IP` | limite de `POST /rules/from-text` par IP et par fenêtre. Non définie : `RATE_LIMIT_PER_IP // 5` (au moins 1) |
| `RATE_LIMIT_LOGIN_PER_IP` | limite de `POST /auth/login` par IP et par fenêtre. Non définie : `RATE_LIMIT_PER_IP // 2` (au moins 3) |
| `TRUSTED_PROXIES` | adresses IP ou réseaux CIDR, séparés par des virgules, des proxys dont l'en-tête `X-Forwarded-For` est lu (Traefik). Non définie : l'IP du pair TCP sert de clé |
| `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL`, `LITELLM_BUDGET_USD` | conversion NL→règle. **Les quatre** doivent être définies, sinon la fonctionnalité est désactivée (`503 nl_feature_disabled`) |
| `CF_EMAIL_ACCOUNT_ID`, `CF_EMAIL_API_TOKEN`, `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO` | alerte e-mail (API REST Cloudflare Email Service) : un récapitulatif des nouvelles corrélations `warning` et `error` après chaque exécution. **Les quatre** doivent être définies, sinon la fonction est désactivée. `CF_EMAIL_ACCOUNT_ID` : identifiant du compte Cloudflare (32 caractères hexadécimaux). `CF_EMAIL_API_TOKEN` : jeton avec la seule permission « Email Sending: Edit ». `ALERT_EMAIL_FROM` : adresse ou `Nom <adresse>` sur un domaine d'envoi déclaré dans Cloudflare (ex. `ChimeraFlow <notifications@notify.linguasolution.com>`) ; `ALERT_EMAIL_TO` : 1 à 5 adresses séparées par des virgules. Une valeur mal formée arrête le démarrage (sans être affichée) |
| `ALERT_EMAIL_COOLDOWN_SECONDS` | délai minimal, en secondes, entre deux e-mails d'alerte (entier ≥ 60). **Obligatoire** dès que les quatre variables d'e-mail ci-dessus sont définies, sinon le démarrage s'arrête. Sans elles, elle est ignorée |

`LITELLM_MODEL` est l'alias du modèle défini sur le proxy LiteLLM (ex. `deepseek-v4.1-flash-group`), sans
préfixe : le client l'envoie tel quel à `LITELLM_BASE_URL` avec `custom_llm_provider="openai"` (le proxy parle le
protocole OpenAI). Un ancien préfixe `openai/` est encore accepté et retiré une seule fois.
`LITELLM_BUDGET_USD` est le plafond **global** de dépense (en USD), suivi dans Redis. Il doit être un
nombre fini strictement positif : `nan`, `inf`, `0` et les valeurs négatives arrêtent le démarrage.

`docker-compose.yml` exige en plus `REDIS_PASSWORD` (mot de passe de Redis, sans valeur par défaut). Il doit
pouvoir figurer dans une URL, par exemple généré avec `openssl rand -hex 24`. Le compose le reprend dans
`REDIS_URL` (`redis://:<mot de passe>@redis:6379/0`).

### Redis en production

Redis porte le budget LLM (clé `chimeraflow:nl:spent_microusd`, **sans expiration**) et les compteurs
du limiteur. Pour un Redis déjà exploité sur le VPS, vérifier :

| Réglage | Valeur | Raison |
|---------|--------|--------|
| `maxmemory-policy` | `noeviction` (ou `volatile-lru` tant que la clé du budget n'a pas de TTL) | Avec `allkeys-lru`, la clé du budget peut être évincée : le budget serait remis à zéro. À saturation, `noeviction` fait échouer les écritures : l'API refuse (`503`) au lieu de laisser passer |
| Persistance | `appendonly yes`, sur un volume | Sans elle, un redémarrage remet budget et compteurs à zéro |
| Authentification | `requirepass` (ou ACL) ; mot de passe dans `REDIS_URL` | Quiconque atteint Redis peut remettre le budget à zéro |
| Exposition | aucun port publié sur l'hôte ; réseau Docker privé | Redis n'est jamais joignable depuis Internet |

Contrôle : `redis-cli CONFIG GET maxmemory-policy`, `CONFIG GET appendonly`, `CONFIG GET requirepass`.
Le `docker-compose.yml` du dépôt applique ces réglages (volume `redis-data`, aucun port publié).

`alembic` charge `config.py` : les variables requises (dont `RATE_LIMIT_*`) doivent aussi être
définies pour les migrations.

Exemple (PowerShell) :

```powershell
$env:DATABASE_URL = "postgresql://user:pass@host/dbname"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:DATA_DIR = "../data"
$env:ACCESS_READER = "access-parser"
$env:RATE_LIMIT_PER_IP = "10"
$env:RATE_LIMIT_WINDOW_SECONDS = "60"
$env:AUTH_TOKEN_SECRET = "<au moins 32 caractères aléatoires>"
$env:DEMO_LOGIN_EMAIL = "demo@example.com"
$env:DEMO_LOGIN_PASSWORD_HASH = "<sortie de python -m auth.hash_password>"
```

### 3. Générer les données synthétiques

```powershell
# Depuis la racine du projet
python scripts/generate_excel.py
python scripts/generate_momo.py              # avec une graine fixe : même sortie à chaque exécution
python scripts/generate_whatsapp.py
cscript //Nologo scripts/generate_access_windows.vbs   # Windows uniquement
```

### 4. Créer le schéma et lancer le serveur

Le schéma est géré par Alembic. Le point d'entrée du conteneur exécute la migration. En local, la lancer
une fois (et après chaque nouvelle révision) avant de démarrer le serveur :

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Documentation de l'API : http://localhost:8000/docs (hors production : elle n'est pas servie quand
`BACKEND_NODE_ENV=production`, voir Authentification).

## Endpoints

Tous les endpoints `/api/v1` sauf `POST /api/v1/auth/login` exigent `Authorization: Bearer <jeton>`.
`/` et `/health` sont publics.

### Authentification (`/api/v1/auth`)

```
POST /api/v1/auth/login   # {email, password} -> {access_token, token_type: "bearer", expires_in} (limité par IP)
GET  /api/v1/auth/me      # compte du jeton présenté : {email}
```

### Sources (`/api/v1/sources`)

```
GET  /api/v1/sources                   # liste des sources et de leur état
GET  /api/v1/sources/{source}/health   # contrôle de santé d'une source
GET  /api/v1/sources/all/records       # records de toutes les sources (limit_per_source)
GET  /api/v1/sources/{source}/records  # records d'une source (limit)
```

### Règles (`/api/v1/rules`)

```
GET    /api/v1/rules/predefined     # les 5 règles prédéfinies (statut stocké)
POST   /api/v1/rules/from-text      # conversion NL→règle : renvoie un brouillon, ne stocke rien (limite par IP, plus stricte)
POST   /api/v1/rules                # création d'une règle (validée ; 409 si l'id existe ou est prédéfini) (limité par IP)
GET    /api/v1/rules                # liste (filtre status)
GET    /api/v1/rules/{id}           # une règle
DELETE /api/v1/rules/{id}           # suppression de la règle et de ses corrélations (limité par IP)
```

### Corrélations (`/api/v1/correlations`)

```
POST /api/v1/correlations/execute   # exécute les règles actives (paramètre rule_ids, 20 au maximum) (limité par IP)
GET  /api/v1/correlations           # liste (filtres rule_id, severity, since ; limit de 1 à 1000)
GET  /api/v1/correlations/stream    # flux SSE des nouvelles corrélations (en-tête Bearer, lu avec fetch)
```

Chaque corrélation porte `explanation` (pourquoi les records correspondent : entité, nom comparé, score, méthode,
conditions et valeurs). Une exécution garde la ligne, l'`id` et le `detected_at` d'une corrélation retrouvée :
`since` et le flux ne livrent donc que les nouvelles.

**Flux temps réel.** `EventSource` ne sait pas envoyer l'en-tête `Authorization` : le client lit le flux avec
`fetch` (aucun jeton de flux, aucun jeton dans une URL). Événements : `ready`, `correlation` (`id:` = id de la
corrélation), `execution`, `end` (fermeture après 300 s ; se reconnecter avec `Last-Event-ID`). Interrogation de la
base toutes les 2 s, 20 flux ouverts au plus. Repli : `GET /api/v1/correlations?since=<ISO 8601>`.

### Bac à sable et démonstration

```
POST /api/v1/normalize      # {text, compare_with[≤20]} -> forme normalisée, mots, nombres, score et méthode par nom comparé
POST /api/v1/demo/reset     # supprime corrélations et exécutions, rétablit les règles prédéfinies (limité par IP)
```

`normalize` n'a pas de limite par IP : sans état, borné (200 caractères, 20 comparaisons) et derrière le jeton.

### Alerte e-mail

Quand `CF_EMAIL_ACCOUNT_ID`, `CF_EMAIL_API_TOKEN`, `ALERT_EMAIL_FROM` et `ALERT_EMAIL_TO` sont définies, une exécution qui produit de
**nouvelles** corrélations `warning` ou `error` envoie un seul e-mail récapitulatif, après la réponse (tâche de
fond : un fournisseur lent ou en panne ne retarde ni ne fait échouer `execute`). Deux essais de 5 s. Un délai
global (`ALERT_EMAIL_COOLDOWN_SECONDS`, clé Redis `chimeraflow:alerts:cooldown` posée avec `SET NX EX`) limite
l'envoi à un récapitulatif par fenêtre, quel que soit le nombre d'exécutions ou de workers. Pendant le délai, les
nouvelles corrélations ne sont pas envoyées plus tard (elles restent visibles dans l'interface). Sans Redis, ou si
Redis est en panne, rien n'est envoyé (échec fermé, journalisé). Les messages
viennent de textes de sources : caractères de contrôle retirés, 300 caractères au plus par ligne, HTML échappé.
Un envoi réussi demande un statut HTTP 2xx et `success: true` dans la réponse ; un échec ne journalise que les
codes d'erreur de Cloudflare. Ni destinataire, ni jeton, ni contenu dans les journaux. Vérification réelle auprès
de Cloudflare Email Service : non faite (voir
`docs/decisions/TECH_DEBT.md`).

La spécification détaillée (corps, réponses, erreurs) est dans `.kiro/specs/api-spec.md`.

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
- Budget : avant chaque appel, le coût estimé (prompt + réponse maximale) est **réservé** dans le compteur Redis
  (`INCRBY`, clé `chimeraflow:nl:spent_microusd`, en micro-USD) ; si la dépense d'avant l'appel atteint
  `LITELLM_BUDGET_USD`, la réservation est rendue et l'appel refusé. Des appels simultanés se voient donc entre
  eux. Après la réponse, la réservation est remplacée par le coût réel : `litellm.completion_cost` ; si LiteLLM ne
  sait pas chiffrer le modèle, estimation à partir des tokens (15 USD par million, volontairement pénalisant).
  Réinitialiser le budget : supprimer la clé Redis. Si Redis ne répond pas, le budget ne peut pas être vérifié
  et la requête est refusée.
  Un appel en échec (délai, erreur du fournisseur, quelle qu'en soit la classe) peut avoir été facturé :
  un coût d'entrée pessimiste (caractères ÷ 4, au même prix) est enregistré.
- Délai : 20 s par appel au fournisseur.
- Les journaux ne contiennent ni le texte, ni la réponse du modèle, ni la clé d'API.

**État réel :** le pipeline est testé avec LiteLLM simulé. Aucun appel à un vrai proxy n'a encore été fait
(voir `docs/decisions/TECH_DEBT.md`).

### Authentification

Un compte de démonstration unique, public, défini par `DEMO_LOGIN_EMAIL` et `DEMO_LOGIN_PASSWORD_HASH`. Aucune
dépendance : `hashlib.scrypt` (hash), `hmac` (HMAC-SHA256 des jetons), `secrets.compare_digest`.

**Créer le hash du mot de passe.** Le mot de passe est lu sur l'entrée standard (jamais en argument, il
resterait dans l'historique du shell) :

```powershell
# Depuis backend/. Le mot de passe fait 8 caractères au moins.
"mot-de-passe-de-demo" | .venv\Scripts\python.exe -m auth.hash_password
# scrypt:32768:8:1:<sel>:<clé>   <- valeur de DEMO_LOGIN_PASSWORD_HASH
```

Le format `scrypt:N:r:p:sel:clé` décrit ses paramètres ; il ne contient pas de `$` et passe donc dans un shell, un
compose ou Doppler sans échappement.

**Session.** `POST /api/v1/auth/login` répond `200` avec un jeton valable `expires_in` secondes (3600). Le jeton
est `<charge utile>.<signature>` (JSON `{v, sub, iat, exp}` signé en HMAC-SHA256 avec `AUTH_TOKEN_SECRET`) : la
signature est vérifiée avant de lire la charge, l'algorithme est fixe. Il n'y a pas de révocation avant
l'expiration ; changer `AUTH_TOKEN_SECRET` (ou `DEMO_LOGIN_EMAIL`) invalide toutes les sessions.

**Erreurs `401`** (avec `WWW-Authenticate: Bearer`) : `auth_invalid_credentials` (login : le même message que
l'email soit inconnu ou le mot de passe faux, le hash est calculé dans les deux cas), `auth_required` (pas de jeton),
`auth_token_invalid` (mal formé, signature fausse, autre compte), `auth_token_expired`.

**Protection.** La dépendance `require_auth` est attachée à l'inclusion des routeurs dans `main.py` : un nouveau
routeur `/api/v1` doit y être inscrit avec elle, et `tests/test_auth.py` vérifie que chaque route `/api/v1` hors login
répond `401` sans jeton.

**Limitation.** `POST /auth/login` a son compteur par IP (`RATE_LIMIT_LOGIN_PER_IP`, plus strict que les mutations).
Le calcul du hash (32 Mio) tourne dans un thread, deux au plus à la fois.

**Documentation interactive.** `/docs`, `/redoc` et `/openapi.json` ne sont pas servis quand
`BACKEND_NODE_ENV=production` : Swagger UI ne peut pas envoyer l'en-tête Bearer au chargement du schéma.

**Journaux.** Ni jeton, ni mot de passe, ni email ne sont journalisés (« Login accepted » / « Login refused »).

### Format des erreurs

Toute erreur applicative a le corps `{"detail": {"code": "<code_stable>", "message": "<message court en anglais>"}}`.
Le client traduit le `code` ; le `message` est une aide pour le développeur et ne s'affiche pas. Les erreurs
de validation de requête (`422`) sont une liste `{loc, msg, type}` sans la valeur rejetée (un mot de passe
n'est jamais renvoyé).

| Code | HTTP | Cas |
|------|------|-----|
| `rule_not_found`, `source_not_found` | 404 | ressource inconnue |
| `rule_already_exists` | 409 | identifiant déjà pris ou réservé (règle prédéfinie) |
| `invalid_status`, `invalid_severity` | 400 | filtre invalide |
| `source_fetch_failed` | 500 | lecture de la source impossible |
| `auth_invalid_credentials` | 401 | login : email ou mot de passe incorrect |
| `auth_required`, `auth_token_invalid`, `auth_token_expired` | 401 | jeton absent, invalide ou expiré |
| `rate_limit_exceeded` | 429 | limite par IP dépassée (en-tête `Retry-After` en secondes) |
| `rate_limit_unavailable` | 503 | Redis du limiteur injoignable : la mutation est refusée |
| `nl_feature_disabled` | 503 | variables `LITELLM_*` incomplètes |
| `nl_budget_exceeded` | 503 | budget LLM épuisé |
| `nl_budget_unavailable` | 503 | compteur de dépense illisible |
| `nl_provider_error` | 502 | le fournisseur LLM a échoué (réseau, délai, HTTP) |
| `nl_conversion_failed` | 422 | aucune règle valide après 2 relances |

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
jamais stockée en base. Une valeur écrite par le client à gauche de l'adresse ajoutée par le proxy est ignorée.
Le stockage en mémoire n'est utilisé que si `BACKEND_NODE_ENV=test`.

`execute` lance uniquement les règles actives (les règles inactives et brouillons sont ignorées) et
**remplace** les corrélations précédentes de chaque règle exécutée : deux exécutions successives donnent la même
liste. La réponse indique `rules_executed`, `rules_failed`, `correlations_found`, `records_scanned` et
`duration_ms`. Une règle en échec garde ses corrélations précédentes ; `rule_executions.error` contient un message
générique et les détails vont dans les journaux. `detected_at` est fixé par l'API, pas par le moteur.

## Records source

Chaque connecteur renvoie des objets `UnifiedRecord` (AGENTS.md §19). Le payload garde les **noms de colonnes
d'origine de la source**, pour que le champ `field` d'une règle et les placeholders `{source.champ}` renvoient à ce
que l'utilisateur voit dans son fichier.

| Source | Champs du payload | Horodatage du record | Entités |
|--------|-------------------|----------------------|---------|
| `excel` | `Produit`, `Prix_Unitaire`, `Fournisseur`, `Date_MAJ` | `Date_MAJ` | `product` |
| `access` | `id`, `designation`, `unite`, `qty_stock`, `prix_achat`, `date_modif` | `date_modif` | `product` |
| `whatsapp` | `author`, `text` | date du message | `product` (mot-clé + quantité, par exemple `ciment 50kg`) |
| `momo` | `transaction_id`, `timestamp`, `phone`, `customer_name`, `operator`, `amount`, `currency`, `status`, `reference`, `quantity` | `timestamp` | `payment`, `product` (tiré de `reference`) |

Les lignes qui ne peuvent pas être lues (produit absent, date invalide, quantité ou montant invalide) sont
sautées, journalisées et comptées dans `parse_errors` du connecteur. Aucune valeur n'est inventée : les mêmes
fichiers donnent toujours les mêmes records (P4).

Le parseur WhatsApp ne lit que le format Android `[JJ/MM/AAAA, HH:MM:SS] Auteur: Message`. Le format iOS et
les messages sur plusieurs lignes sont comptés comme erreurs (voir `TECH_DEBT.md`).

## Serveurs MCP

Chaque source est aussi exposée comme serveur MCP (SDK `mcp`, transport stdio), un processus par source :

| Serveur Kiro | Source | Fichier lu sous `DATA_DIR` |
|---|---|---|
| `chimeraflow-excel` | `excel` | `tarifs_fournisseurs.xlsx` |
| `chimeraflow-access` | `access` | `STOCK_ZOBO.mdb` |
| `chimeraflow-whatsapp` | `whatsapp` | `commandes_clients.txt` |
| `chimeraflow-momo` | `momo` | `momo_transactions.csv` |

Outils (lecture seule) :

- `fetch_records(limit=100)` : `limit` entre 1 et 1000, sinon l'appel est refusé. Renvoie
  `{source, count, parse_errors, records}` avec des `UnifiedRecord`.
- `health_check()` : `status` (`ok`, `degraded`, `error`), `source`, `message`, `last_fetch`.

Une ressource `chimeraflow://source/<source>` décrit la source.

### Lancer un serveur à la main

Depuis la racine du dépôt (Windows, venv du backend) :

```powershell
$env:DATA_DIR = "data"; $env:ACCESS_READER = "access-parser"
backend\.venv\Scripts\python.exe backend\mcp_main.py --source excel
```

Le serveur parle MCP sur stdin/stdout et attend un client. Il se termine à la fermeture de stdin.
Les journaux JSON (`connector`, `operation`, `records_count`, `errors_count`, `duration_ms`) vont sur stderr.
`DATA_DIR` est obligatoire, `ACCESS_READER` l'est pour la source `access` seulement. Aucune valeur par défaut :
une variable manquante ou invalide arrête le processus avec le code 2. Les serveurs n'ont besoin d'aucun autre
réglage de l'API (base de données, Redis, secrets d'authentification).

Sous Linux ou macOS, le Python du venv est `backend/.venv/bin/python`. Dans l'image Docker, le lanceur est
`/app/mcp_main.py` (`docker run -i ... python mcp_main.py --source excel`, `DATA_DIR=/data`).
Aucun port n'est ouvert et aucun service compose ne démarre de serveur MCP.

### Utilisation par Kiro

`.kiro/settings/mcp.json` déclare les quatre serveurs avec le Python du venv
(`backend/.venv/Scripts/python.exe`), `backend/mcp_main.py --source <nom>` et deux variables d'environnement
(`DATA_DIR=data`, `ACCESS_READER=access-parser`). Les chemins sont relatifs à la racine du dépôt, répertoire
de travail de Kiro. Le modèle versionné est `backend/mcp_servers/kiro-mcp.json`, vérifié par
`tests/test_mcp_servers.py`. Les deux outils sont en `autoApprove` car ils sont en lecture seule.

Pour vérifier dans Kiro : ouvrir le panneau MCP (vue « MCP Servers »), les quatre serveurs doivent passer à l'état
connecté avec deux outils chacun. Demander ensuite dans le chat « appelle `health_check` du serveur
chimeraflow-excel » : la réponse contient `status: ok`.

## Schéma de règle

Les règles suivent le format de AGENTS.md §20 :

```json
{
  "id": "r_low_stock",
  "natural_language": "Quand un client demande un produit sur WhatsApp...",
  "trigger": {
    "source": "whatsapp",
    "entity": "product",
    "where": []
  },
  "joins": [
    {
      "source": "access",
      "table": "Articles",
      "on": {"entity": "product", "field": "designation"},
      "where": [{"field": "qty_stock", "op": "lt", "value": 10}]
    },
    {
      "source": "excel",
      "sheet": "Tarifs",
      "on": {"entity": "product", "field": "Produit"},
      "where": [{"field": "Prix_Unitaire", "op": "gt", "ref": "access.prix_achat", "tolerance_pct": 10}]
    }
  ],
  "window_seconds": 604800,
  "emit": {
    "severity": "warning",
    "template": "{product}: stock {access.qty_stock}, prix {excel.Prix_Unitaire} FCFA"
  }
}
```

Règles de validation : de 1 à 10 joins ; un join `access` exige `table` ; un join `excel` exige `sheet` ; `on.field`
est obligatoire ; 10 conditions au plus par liste ; `value` : scalaire de 200 caractères au plus ou liste de 50
éléments au plus ; `template` : 500 caractères au plus. Les clés inconnues d'une condition sont refusées.

**Opérateurs autorisés** (liste blanche de sécurité) :
`eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`

**Vocabulaire fermé** (de la donnée, jamais du code) :

- `trigger.where` : conditions sur le record déclencheur (valeur littérale seulement). Un record qui ne les satisfait pas ne donne rien.
- `ref` : le côté droit d'une condition est `"<source>.<colonne>"`, un record déjà apparié (le déclencheur ou un join
  précédent). Exclusif avec `value` ; interdit dans `trigger.where` et avec `in`.
- `tolerance_pct` (0 à 1000, avec `ref` et `lt`, `lte`, `gt`, `gte`) : compare l'écart relatif `|champ − ref| / |ref|`
  en pourcentage à la tolérance. Un `ref` nul, absent ou égal à zéro rend la condition fausse.
- `on.field: "entities"` : le join compare l'entité du déclencheur à chaque entité du record joint (les produits d'un message WhatsApp).
- Les colonnes (`field`, `on.field`, `ref`, placeholders) doivent exister dans leur source (`schemas/sources.py`). Un
  `template` n'expose jamais `momo.phone` ni `momo.customer_name`. Un brouillon du modèle de langage qui invente une
  colonne est refusé puis relancé avec l'erreur.

## Moteur de règles

### Interpréteur (`engine/interpreter.py`)

- Exécute les règles sur des records unifiés.
- Fenêtre temporelle : un record joint doit se situer à `window_seconds` **avant ou après** le record déclencheur
  (les données de référence, comme les prix, sont souvent antérieures au message).
- Suit la provenance (propriété P1) : chaque corrélation liste le record déclencheur et chaque record joint.
- Corrèle **chaque produit** d'un message (un message qui demande deux produits donne deux corrélations ; deux
  écritures du même produit comptent pour une).
- `explanation` par corrélation : entité du déclencheur, record joint, nom comparé, score, méthode (`exact`,
  `synonym`, `fuzzy`, `token`), nombre de candidats, conditions avec `expected`, `actual` et `gap_pct`.
- N'accepte que les opérateurs de la liste blanche (R5).
- Une comparaison `where` entre types incompatibles (par exemple texte et nombre) est un non-match, pas une erreur.
- Déterministe (propriété P4) : la sortie ne dépend que des entrées (pas d'heure de détection).
- Quand plusieurs records d'une source jointe correspondent, le meilleur est choisi : score de similarité le plus
  élevé, puis record situé avant ou à l'instant du déclencheur, puis le plus proche dans le temps (le dernier prix
  l'emporte parmi les doublons), puis ordre de la source.
- Les templates sont rendus en une seule passe : un texte de source qui ressemble à `{momo.phone}` n'est pas
  développé, et un placeholder sans valeur devient une chaîne vide.
- Un horodatage source sans fuseau horaire est interprété en UTC.

### Normaliseur (`engine/normalizer.py`)

`normalize_text()` est l'implémentation unique ; les connecteurs l'appellent par
`BaseConnector.normalize_text()`. Étapes, dans l'ordre :

1. minuscules
2. suppression des accents
3. décimales et fractions gardées en un seul jeton (`2.5` devient `2-5`, `1/2` devient `1-2`)
4. suppression de la ponctuation (tirets conservés)
5. séparation des lettres et des chiffres (`50kg` devient `50 kg`)
6. réduction des espaces, en dernier, pour que le résultat soit idempotent (P2)

La mise en correspondance (`match_detail`) ajoute les synonymes FR/EN, une similarité floue pour les fautes de
frappe (Levenshtein normalisé, `rapidfuzz`, seuil **0.85**, fautes tolérées seulement dans les mots d'au moins 5
lettres : `tuyau PVC 32mm` n'est pas `tuyau PPR 32mm`) et l'**inclusion de mots** pour les noms partiels : `tuyau PVC`
correspond à `Tuyau PVC Ø 32mm (barre 6m)` et `perceuse 500W` à `Perceuse électrique 500W` (méthode `token`, score de
0.85 à 0.99, jamais devant une correspondance exacte). Garde numérique : deux noms dont les nombres diffèrent ne
correspondent pas (`ciment 50 kg` et `ciment 40 kg`, ou `Ciment-colle 25 kg`, même si la similarité vaut 0.92),
sauf qu'un nom qui a moins de nombres, tous présents dans l'autre, peut y correspondre par inclusion. Le détail
est dans `.kiro/specs/design.md` §4.

Exemple :
```python
from engine.normalizer import normalize_text

# Le scénario de démonstration : un produit écrit de quatre façons
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

```powershell
.venv\Scripts\python.exe -m engine.validate_rules            # <DATA_DIR>/rules
.venv\Scripts\python.exe -m engine.validate_rules ..\data\rules
```

Le hook `.kiro/hooks/rule-validate.json` se déclenche à l'enregistrement d'un fichier de `data/rules/`.

Cinq règles prédéfinies, toutes actives :

1. **r_low_stock** : alerte de stock faible (démonstration)
2. **r_payment_received** : paiement Mobile Money `SUCCESS` (`trigger.where`) rapproché d'une commande WhatsApp (jointure sur `entities`)
3. **r_price_comparison** : écart de plus de 10 % entre le prix d'achat Access et le tarif Excel (`ref` + `tolerance_pct`)
4. **r_high_value_order** : suivi des commandes à forte valeur
5. **r_stock_replenish** : stock Access inférieur à 15 (`trigger.where`) avec commande WhatsApp récente

Le seed insère une règle absente. Pour une règle existante dont la définition livrée a changé, il met à jour la
définition, incrémente `version` **et applique le statut du fichier** : c'est ainsi qu'une version réactive une règle
corrigée. Une règle inchangée garde son statut stocké (un choix en base survit au redémarrage).
`POST /api/v1/demo/reset` rétablit tout. Sur les données livrées, chacune des cinq règles produit au moins une
corrélation (`tests/test_scenario_data.py`).

## Base de données

Modèles SQLAlchemy :

- **Rule** : définition d'une règle de corrélation
- **RuleExecution** : historique des exécutions (durée, records lus)
- **Correlation** : corrélation émise, avec sa provenance

`DATABASE_URL` est requise (pas de repli vers SQLite). PostgreSQL (Neon) en production. Les tables sont créées
et les règles prédéfinies sont insérées ou mises à jour dans `rules` au démarrage ; le démarrage échoue si l'un
des deux est impossible. Les corrélations et exécutions référencent `rules.id` avec `ON DELETE CASCADE` : supprimer
une règle supprime ses résultats. Les clés étrangères sont aussi appliquées sur SQLite (les tests se comportent
comme PostgreSQL). Chaque règle s'exécute dans son propre savepoint : une règle en échec ne laisse aucune
corrélation partielle. Les horodatages sont stockés en UTC avec fuseau.

## Tests

Lancer depuis `backend/`. `tests/conftest.py` définit les variables d'environnement de test
(`BACKEND_NODE_ENV=test`, `DATA_DIR`, `DATABASE_URL` SQLite en mémoire, `CORS_ORIGINS`, `RATE_LIMIT_PER_IP`,
`RATE_LIMIT_WINDOW_SECONDS`) : aucun fichier `.env` n'est nécessaire. `BACKEND_NODE_ENV=test` sélectionne aussi
le stockage mémoire du limiteur (choix explicite, pas un repli).

```powershell
# Tous les tests
.venv\Scripts\python.exe -m pytest tests -v

# Tests de contrat (R1 à R4)
.venv\Scripts\python.exe -m pytest tests\test_connectors.py -v

# Tests basés sur les propriétés (Hypothesis)
.venv\Scripts\python.exe -m pytest tests\test_properties.py tests\test_normalizer.py -v
```

Le test de contrat Access est sauté quand `mdb-export` (mdbtools) n'est pas installé.

Les tests des serveurs MCP (`tests/test_mcp_servers.py`) pilotent le serveur avec le client du SDK, en mémoire pour
la plupart. Quatre tests lancent le vrai lanceur en sous-processus (stdio) et l'arrêtent à la fin du test. Un démarrage
à froid importe pandas et le SDK : compter plusieurs secondes par processus.

## Sécurité

Selon AGENTS.md §1 (règles de sécurité) :

- Implémenté : **aucune exécution de code** (les règles sont du JSON, interprété avec des opérateurs en liste blanche)
- Implémenté : **validation des entrées** avec des schémas Pydantic stricts
- Implémenté : les détails d'erreur des sources sont journalisés, jamais renvoyés dans les réponses HTTP
- Implémenté : **limitation par IP** sur chaque endpoint de mutation (slowapi + Redis), 429 avec `Retry-After`
- Implémenté : **plafond de budget LLM** (`LITELLM_BUDGET_USD`, compteur de dépense dans Redis, refus une fois dépassé)
- Implémenté : texte utilisateur séparé des instructions dans le prompt LLM, réponse du modèle validée par `RuleCreate`
- Implémenté : aucune adresse IP, aucun texte utilisateur et aucune clé API dans les journaux du nouveau code
  (l'avertissement de slowapi, qui contient l'IP, est désactivé)
- **Non implémenté** : assainissement des textes de source avant affichage (travail frontend)
- Implémenté : **authentification** de tous les endpoints `/api/v1` (jeton Bearer, compte de démonstration unique),
  connexion limitée par IP, `/docs` absent en production (voir Authentification)

## Développement

### Ajouter un connecteur

1. Créer `backend/mcp_servers/mon_connecteur.py`
2. Hériter de `BaseConnector`
3. Implémenter `fetch_records()` et `_perform_health_check()`
4. Renvoyer des `UnifiedRecord` avec les noms de colonnes d'origine dans le payload
5. Ajouter les tests dans `tests/test_connectors.py`
6. Pour l'exposer en MCP : l'ajouter à `SOURCES` (`mcp_settings.py`) et à `build_connector` (`mcp_app.py`), puis
   déclarer le serveur dans `kiro-mcp.json`

### Ajouter une règle

Via l'API (`POST /api/v1/rules`, éventuellement à partir d'un brouillon de `POST /api/v1/rules/from-text`), ou,
pour une règle prédéfinie, en ajoutant `data/rules/r_ma_regle.json` (format ci-dessus) puis en lançant
`python -m engine.validate_rules`. Le seed l'insère au prochain démarrage.

---

**Phase** : P2 (moteur de règles), en cours. Faits : interpréteur, normaliseur, API règles et corrélations,
limitation par IP et conversion NL→règle implémentés. Extensions du DSL en attente.
