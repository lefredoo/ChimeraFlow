# Spécification de l'API REST (FastAPI)

Liste des endpoints définis dans `backend/main.py` et `backend/api/*.py` au 2026-11-14.
Seuls les endpoints présents dans le code figurent ici. Aucun endpoint de conversion vers
la base n'existe. La documentation interactive est générée par FastAPI (`/docs`, `/redoc`,
`/openapi.json`) et n'est pas servie quand `BACKEND_NODE_ENV=production`.

**Authentification.** Tous les endpoints `/api/v1` exigent l'en-tête `Authorization: Bearer <jeton>`,
sauf `POST /api/v1/auth/login`. Seuls `GET /` et `GET /health` sont publics. Le jeton s'obtient par
`POST /api/v1/auth/login` (§2.1) et expire au bout d'une heure.

Toutes les réponses JSON sont en UTF-8. Les dates sont des chaînes ISO 8601.

---

## 1. Conventions

### 1.1 Erreurs applicatives

```json
{"detail": {"code": "rule_not_found", "message": "Rule not found"}}
```

- `code` est stable : le client traduit ce code. `message` est une aide pour le développeur, en anglais, à ne pas afficher.
- Les réponses `401` portent `WWW-Authenticate: Bearer`.
- Les erreurs `nl_*` ajoutent `fallback_rules` (liste de `RuleResponse`, les règles prédéfinies) dans `detail`.
- Les erreurs de validation de requête (`422`) sont une liste `{"detail": [{"loc", "msg", "type"}]}` : le format de FastAPI sans la valeur rejetée (`input`), pour ne pas renvoyer un mot de passe.

| Code | HTTP | Endpoint(s) | Cas |
|------|------|-------------|-----|
| `auth_invalid_credentials` | 401 | auth/login | email inconnu ou mot de passe faux (même réponse dans les deux cas) |
| `auth_required` | 401 | tous les endpoints `/api/v1` sauf login | en-tête `Authorization: Bearer` absent |
| `auth_token_invalid` | 401 | idem | jeton mal formé, signature fausse ou compte inconnu |
| `auth_token_expired` | 401 | idem | jeton authentique mais expiré |
| `source_not_found` | 404 | sources/{source}/health, sources/{source}/records | source inconnue (`excel`, `access`, `whatsapp`, `momo`) |
| `source_fetch_failed` | 500 | sources/{source}/records | lecture du fichier impossible |
| `rule_not_found` | 404 | rules/{id} (GET, DELETE) | règle absente |
| `rule_already_exists` | 409 | POST /rules | identifiant déjà pris ou réservé à une règle prédéfinie |
| `invalid_status` | 400 | GET /rules | filtre `status` inconnu |
| `invalid_severity` | 400 | GET /correlations | filtre `severity` inconnu |
| `rate_limit_exceeded` | 429 | endpoints limités | limite par IP dépassée. En-tête `Retry-After` (secondes) |
| `rate_limit_unavailable` | 503 | endpoints limités | Redis du limiteur injoignable : la mutation est refusée |
| `nl_feature_disabled` | 503 | POST /rules/from-text | variables `LITELLM_*` incomplètes |
| `nl_budget_exceeded` | 503 | POST /rules/from-text | budget LLM épuisé |
| `nl_budget_unavailable` | 503 | POST /rules/from-text | compteur de dépense illisible |
| `nl_provider_error` | 502 | POST /rules/from-text | fournisseur LLM en échec (réseau, délai, HTTP) |
| `nl_conversion_failed` | 422 | POST /rules/from-text | aucune règle valide après 2 relances |

### 1.2 Limitation par IP

Limitées : `POST /api/v1/auth/login` (limite `RATE_LIMIT_LOGIN_PER_IP`, plus stricte), `POST /api/v1/rules`, `DELETE /api/v1/rules/{rule_id}`,
`POST /api/v1/correlations/execute` (limite `RATE_LIMIT_PER_IP` par `RATE_LIMIT_WINDOW_SECONDS`)
et `POST /api/v1/rules/from-text` (limite `RATE_LIMIT_NL_PER_IP`). Une requête refusée par la
validation (422) n'est pas comptée. Toutes les lectures (GET) ne sont pas limitées.

### 1.3 Schémas de données

**RuleCreate** (corps de `POST /api/v1/rules`, et `rule` de la réponse de `from-text`) :

| Champ | Type | Contraintes |
|-------|------|-------------|
| `id` | string | `^[a-z0-9_]+$`, 1 à 100 caractères |
| `natural_language` | string | 10 à 1000 caractères |
| `trigger` | objet | `source` ∈ `whatsapp`, `momo`, `excel`, `access` ; `entity` : string |
| `joins` | tableau | 1 à 10 éléments, voir RuleJoin |
| `window_seconds` | entier | 60 à 2 592 000 ; défaut 604 800 |
| `emit` | objet | `severity` ∈ `info`, `warning`, `error` ; `template` : string |

**RuleJoin** : `source` (mêmes valeurs que `trigger.source`), `table` (obligatoire si `access`),
`sheet` (obligatoire si `excel`), `on` (objet `{"entity": "product", "field": "<colonne>"}`),
`where` (tableau, défaut vide) de `{field, op, value}` avec `op` ∈ `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`.

**RuleResponse** : `id`, `version`, `status` (`active`, `inactive`, `draft`), `natural_language`,
`trigger`, `joins`, `window_seconds`, `emit`, `created_at`, `updated_at`.

**CorrelationResponse** : `id` (entier), `rule_id`, `detected_at`, `severity`, `message`,
`provenance` (liste de `{source, source_ref, record_id}`).

---

## 2. Système

### GET /
Renvoie les liens de l'API.

- **Limite** : aucune.
- **Réponse 200** : `{"message": "ChimeraFlow API", "docs": "/docs", "health": "/health", "endpoints": {"auth": "/api/v1/auth", "sources": "/api/v1/sources", "rules": "/api/v1/rules", "correlations": "/api/v1/correlations"}}`. `docs` vaut `null` en production.

### GET /health
Contrôle de vie du processus. Public.

- **Limite** : aucune.
- **Réponse 200** : `{"status": "ok", "service": "chimeraflow-api", "version": "0.1.0", "environment": "<BACKEND_NODE_ENV ou null>"}`

### 2.1 Authentification (`/api/v1/auth`)

Un seul compte de démonstration, public (`DEMO_LOGIN_EMAIL`, hash dans `DEMO_LOGIN_PASSWORD_HASH`).

#### POST /api/v1/auth/login
Échange les identifiants contre un jeton. Public.

- **Corps** : `{"email": "<1 à 254 caractères>", "password": "<1 à 256 caractères>"}`. Aucun autre champ. L'email est comparé sans casse ni espaces de bord.
- **Limite** : `RATE_LIMIT_LOGIN_PER_IP` par IP et par fenêtre.
- **Réponse 200** : `{"access_token": "<jeton>", "token_type": "bearer", "expires_in": 3600}`
- **Erreurs** : 401 `auth_invalid_credentials` ; 422 validation ; 429 `rate_limit_exceeded` (`Retry-After`) ; 503 `rate_limit_unavailable`.

#### GET /api/v1/auth/me
- **Limite** : aucune.
- **Réponse 200** : `{"email": "<compte du jeton>"}`
- **Erreurs** : 401 `auth_required`, `auth_token_invalid`, `auth_token_expired`.

---

## 3. Sources (`/api/v1/sources`)

Les connecteurs sont lus dans `DATA_DIR` : `tarifs_fournisseurs.xlsx`, `STOCK_ZOBO.mdb`
(table `Articles`), `commandes_clients.txt`, `momo_transactions.csv`.

### GET /api/v1/sources
Liste les sources et leur état. Lance un contrôle de santé de chacune (résultat mis en cache 30 s).

- **Limite** : aucune.
- **Réponse 200** : `{"sources": [{"name": "excel", "status": "ok|error|...", "message": "", "last_fetch": null}, ...]}`

### GET /api/v1/sources/{source}/health
- **Paramètre de chemin** : `source` ∈ `excel`, `access`, `whatsapp`, `momo`.
- **Limite** : aucune.
- **Réponse 200** : dictionnaire renvoyé par le connecteur (`status`, `source`, `message`, `last_fetch`).
- **Erreurs** : 404 `source_not_found`.

### GET /api/v1/sources/all/records
Lit les records de toutes les sources.

- **Paramètre de requête** : `limit_per_source` (entier, 1 à 500, défaut 50).
- **Limite** : aucune.
- **Réponse 200** : `{"total_records": <int>, "records": [UnifiedRecord...], "errors": null | [{"source": "...", "error": "Failed to fetch records from source"}]}`. Une source en échec n'arrête pas les autres.

### GET /api/v1/sources/{source}/records
- **Paramètre de chemin** : `source` (voir ci-dessus).
- **Paramètre de requête** : `limit` (entier, 1 à 1000, défaut 100).
- **Limite** : aucune.
- **Réponse 200** : `{"source": "<nom>", "count": <int>, "records": [UnifiedRecord...]}`
- **Erreurs** : 404 `source_not_found` ; 500 `source_fetch_failed`.

**UnifiedRecord** : `id`, `source`, `source_ref`, `timestamp`, `lang`, `entities` (`{type, raw, norm}`), `payload` (champs d'origine de la source).

---

## 4. Règles (`/api/v1/rules`)

### GET /api/v1/rules/predefined
Règles chargées depuis `data/rules/*.json` et seedées au démarrage. Renvoie le statut stocké, trié par `id`.

- **Limite** : aucune.
- **Réponse 200** : tableau de RuleResponse (5 éléments).

### POST /api/v1/rules/from-text
Convertit une phrase en brouillon de règle. **Ne stocke rien.** Le client relit le brouillon puis appelle `POST /api/v1/rules`.

- **Corps** : `{"text": "<20 à 1000 caractères, espaces de début et de fin retirés>", "language": "fr" | "en"}` (défaut `fr`).
- **Limite** : `RATE_LIMIT_NL_PER_IP` par IP et par fenêtre.
- **Réponse 200** : `{"rule": RuleCreate, "retries": <0 à 2>}`. Le `rule.id` est généré (`r_nl_<12 hex>`) et `natural_language` reprend le texte de l'utilisateur.
- **Erreurs** : 422 validation du corps ou `nl_conversion_failed` ; 429 `rate_limit_exceeded` ; 502 `nl_provider_error` ; 503 `nl_feature_disabled`, `nl_budget_exceeded`, `nl_budget_unavailable`, `rate_limit_unavailable`. Les erreurs `nl_*` contiennent `fallback_rules`.

Le modèle ne reçoit le texte que comme donnée. La réponse du modèle est validée par `RuleCreate`. Aucun code n'est exécuté (voir design.md §9).

### POST /api/v1/rules
Crée une règle active, à partir d'une définition complète.

- **Corps** : RuleCreate.
- **Limite** : `RATE_LIMIT_PER_IP` par IP et par fenêtre.
- **Réponse 201** : RuleResponse (`version` 1, `status` `active`).
- **Erreurs** : 409 `rule_already_exists` (identifiant existant ou prédéfini, même supprimé) ; 422 validation ; 429 ; 503 `rate_limit_unavailable`.

### GET /api/v1/rules
Liste les règles.

- **Paramètre de requête** : `status` (optionnel) : `active`, `inactive` ou `draft` (noms exacts de l'enum).
- **Limite** : aucune.
- **Réponse 200** : tableau de RuleResponse, trié par `id`.
- **Erreurs** : 400 `invalid_status`.

### GET /api/v1/rules/{rule_id}
- **Limite** : aucune.
- **Réponse 200** : RuleResponse.
- **Erreurs** : 404 `rule_not_found`.

### DELETE /api/v1/rules/{rule_id}
Supprime la règle et ses corrélations (cascade). Une règle prédéfinie supprimée réapparaît au prochain démarrage.

- **Limite** : `RATE_LIMIT_PER_IP` par IP et par fenêtre (un seul compteur pour tous les identifiants).
- **Réponse 204** : sans corps.
- **Erreurs** : 404 `rule_not_found` ; 429 ; 503 `rate_limit_unavailable`.

---

## 5. Corrélations (`/api/v1/correlations`)

### POST /api/v1/correlations/execute
Exécute les règles actives (ou celles demandées) sur les données courantes. Chaque règle exécutée **remplace** ses corrélations précédentes.

- **Paramètre de requête** : `rule_ids` (répétable : `?rule_ids=a&rule_ids=b`), 20 au maximum. Sans paramètre : toutes les règles `active`. Les règles `inactive` ne sont jamais exécutées.
- **Corps** : aucun.
- **Limite** : `RATE_LIMIT_PER_IP` par IP et par fenêtre.
- **Réponse 200**, aucune règle à exécuter :
  `{"status": "no_rules", "message": "No active rules to execute", "rules_executed": 0, "rules_failed": 0, "correlations_found": 0}`
- **Réponse 200**, exécution :
  `{"status": "success", "rules_executed": <int>, "rules_failed": <int>, "correlations_found": <int>, "records_scanned": <int>, "duration_ms": <int>}`
  `records_scanned` est le nombre total de records lus. Une règle en échec est comptée dans `rules_failed` et garde ses corrélations précédentes ; son détail n'est jamais renvoyé (journaux seulement).
- **Erreurs** : 422 si plus de 20 `rule_ids` ; 429 ; 503 `rate_limit_unavailable`.

### GET /api/v1/correlations
- **Paramètres de requête** : `rule_id` (optionnel), `severity` (optionnel : `info`, `warning`, `error`), `limit` (1 à 1000, défaut 100).
- **Limite** : aucune.
- **Réponse 200** : tableau de CorrelationResponse, les plus récentes d'abord (`detected_at` décroissant).
- **Erreurs** : 400 `invalid_severity` ; 422 si `limit` est hors bornes.

---

## 6. Sécurité (état réel)

- **Authentification par jeton Bearer** sur tous les endpoints `/api/v1` (lectures et mutations), sauf le login. Jeton signé HMAC-SHA256 par `AUTH_TOKEN_SECRET`, valable 1 h, sans révocation avant l'expiration. Compte unique et public : il protège contre l'accès anonyme et les robots, pas contre un utilisateur qui connaît le mot de passe affiché (voir TECH_DEBT).
- Le login est limité par IP (`RATE_LIMIT_LOGIN_PER_IP`) et renvoie la même réponse que l'email soit inconnu ou le mot de passe faux. Ni jeton, ni mot de passe, ni email dans les journaux ni dans les réponses d'erreur.
- CORS : liste blanche `CORS_ORIGINS`, méthodes et en-têtes ouverts (`*`), identifiants autorisés. `Retry-After` est exposé au navigateur.
- Documentation `/docs`, `/redoc` et `/openapi.json` : non servies quand `BACKEND_NODE_ENV=production`, servies sinon (Swagger UI ne peut pas envoyer le jeton au chargement du schéma).
- L'IP du client n'est jamais stockée (migration `0002`).
