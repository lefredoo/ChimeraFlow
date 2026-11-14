# Backend ChimeraFlow

API FastAPI du moteur de corrélation.

## Architecture

```
backend/
├── api/                    # endpoints REST
│   ├── sources.py          # GET /api/v1/sources (P1)
│   ├── rules.py            # POST /rules, POST /rules/from-text, GET /rules
│   ├── correlations.py     # POST /correlations/execute, GET /correlations
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
│   ├── nl_budget.py        # compteur de dépense LLM (Redis)
│   └── llm_client.py       # frontière LiteLLM (import à la demande)
├── mcp_servers/            # connecteurs de sources (P1)
│   ├── base.py             # BaseConnector et schéma UnifiedRecord
│   ├── excel_connector.py  # lecture Excel (pandas + openpyxl)
│   ├── access_connector.py # lecture Access (CLI mdbtools ou access-parser, selon ACCESS_READER)
│   ├── whatsapp_connector.py # parseur WhatsApp (expression régulière, format Android)
│   └── momo_connector.py   # lecture du CSV Mobile Money
├── migrations/             # migrations Alembic (env.py lit DATABASE_URL)
├── models/                 # modèles SQLAlchemy (P2)
│   ├── base.py             # configuration de la base (clés étrangères activées sur SQLite)
│   ├── rule.py             # Rule, RuleExecution, Correlation
│   └── seed.py             # seed idempotent des règles prédéfinies au démarrage
├── schemas/                # validation Pydantic (P2)
│   └── rule.py             # RuleCreate, RuleResponse, etc.
├── tests/                  # tests (voir tests/README.md)
│   ├── conftest.py         # variables d'environnement de test, profils Hypothesis, fixture api_client
│   ├── factories.py        # records unifiés en mémoire pour les tests du moteur et de l'API
│   ├── test_api_correlations.py # seed, exécution, clés étrangères, idempotence
│   ├── test_connectors.py  # tests de contrat (R1 à R4)
│   ├── test_connector_payloads.py # noms de champs, entités, erreurs de parsing
│   ├── test_access_readers.py # mdbtools et access-parser produisent les mêmes records
│   ├── test_migrations.py  # alembic upgrade head / downgrade base, pas de dérive avec les modèles
│   ├── test_properties.py  # tests basés sur les propriétés (Hypothesis)
│   ├── test_normalizer.py  # variantes de normalisation, idempotence, nombres
│   ├── test_interpreter.py # exécution des règles, provenance, choix du meilleur candidat, rendu des templates
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

**Facultatives** (le comportement associé est désactivé, ou laissé au défaut de la bibliothèque, quand elles ne sont pas définies)

| Variable | Rôle |
|----------|------|
| `BACKEND_NODE_ENV` | `development`, `production` ou `test` |
| `BACKEND_PORT` | port utilisé par `python main.py` (défaut d'uvicorn si absent) |
| `BACKEND_LOG_LEVEL` | niveau de journalisation |
| `RATE_LIMIT_NL_PER_IP` | limite de `POST /rules/from-text` par IP et par fenêtre. Non définie : `RATE_LIMIT_PER_IP // 5` (au moins 1) |
| `TRUSTED_PROXIES` | adresses IP ou réseaux CIDR, séparés par des virgules, des proxys dont l'en-tête `X-Forwarded-For` est lu (Traefik). Non définie : l'IP du pair TCP sert de clé |
| `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL`, `LITELLM_BUDGET_USD` | conversion NL→règle. **Les quatre** doivent être définies, sinon la fonctionnalité est désactivée (`503 nl_feature_disabled`) |

`LITELLM_MODEL` est une chaîne de modèle LiteLLM. Pour un proxy LiteLLM, utiliser
`openai/<alias du modèle sur le proxy>` avec `LITELLM_BASE_URL` = URL du proxy.
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

Documentation de l'API : http://localhost:8000/docs

## Endpoints

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
GET  /api/v1/correlations           # liste (filtres rule_id, severity ; limit de 1 à 1000)
```

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
- Budget : avant chaque appel, la dépense cumulée (Redis, clé `chimeraflow:nl:spent_microusd`, en micro-USD)
  est comparée à `LITELLM_BUDGET_USD`. Le coût d'un appel vient de `litellm.completion_cost` ; si LiteLLM ne
  sait pas chiffrer le modèle, il est estimé à partir des tokens (15 USD par million, volontairement pénalisant).
  Réinitialiser le budget : supprimer la clé Redis. Si Redis ne répond pas, le budget ne peut pas être vérifié
  et la requête est refusée.
  Un appel en échec (délai, erreur du fournisseur, quelle qu'en soit la classe) peut avoir été facturé :
  un coût d'entrée pessimiste (caractères ÷ 4, au même prix) est enregistré.
- Délai : 20 s par appel au fournisseur.
- Les journaux ne contiennent ni le texte, ni la réponse du modèle, ni la clé d'API.

**État réel :** le pipeline est testé avec LiteLLM simulé. Aucun appel à un vrai proxy n'a encore été fait
(voir `docs/decisions/TECH_DEBT.md`).

### Format des erreurs

Toute erreur applicative a le corps `{"detail": {"code": "<code_stable>", "message": "<message court en anglais>"}}`.
Le client traduit le `code` ; le `message` est une aide pour le développeur et ne s'affiche pas. Les erreurs
de validation de requête (`422` de FastAPI) gardent le format liste de FastAPI.

| Code | HTTP | Cas |
|------|------|-----|
| `rule_not_found`, `source_not_found` | 404 | ressource inconnue |
| `rule_already_exists` | 409 | identifiant déjà pris ou réservé (règle prédéfinie) |
| `invalid_status`, `invalid_severity` | 400 | filtre invalide |
| `source_fetch_failed` | 500 | lecture de la source impossible |
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

## Schéma de règle

Les règles suivent le format de AGENTS.md §20 :

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

Règles de validation : de 1 à 10 joins ; un join `access` exige `table` ; un join `excel` exige `sheet`.

**Opérateurs autorisés** (liste blanche de sécurité) :
`eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`

## Moteur de règles

### Interpréteur (`engine/interpreter.py`)

- Exécute les règles sur des records unifiés.
- Fenêtre temporelle : un record joint doit se situer à `window_seconds` **avant ou après** le record déclencheur
  (les données de référence, comme les prix, sont souvent antérieures au message).
- Suit la provenance (propriété P1) : chaque corrélation liste le record déclencheur et chaque record joint.
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

La mise en correspondance ajoute les synonymes FR/EN et une similarité floue : distance de Levenshtein
normalisée (`rapidfuzz`), seuil **0.85**. Deux entités ne correspondent que si elles contiennent les mêmes
nombres : `ciment 50 kg` ne correspond jamais à `ciment 40 kg`, même si leur similarité vaut 0.92.

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

Cinq règles prédéfinies :

1. **r_low_stock** : alerte de stock faible (démonstration), active
2. **r_payment_received** : confirmation de paiement, **inactive**
3. **r_price_comparison** : détection d'écart de prix, **inactive**
4. **r_high_value_order** : suivi des commandes à forte valeur, active
5. **r_stock_replenish** : recommandation de réapprovisionnement, **inactive**

Les règles 2, 3 et 5 sont seedées inactives : le DSL ne sait pas exprimer ce que leur description promet (filtre
de statut, écart supérieur à 10 %, seuil de stock sur le record déclencheur). Activer une règle est un changement
de statut dans la table `rules` ; le seed garde ce choix au redémarrage. Voir `docs/decisions/TECH_DEBT.md`.

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
- **Non implémenté** : authentification des endpoints (voir `.kiro/specs/api-spec.md` §6)

## Développement

### Ajouter un connecteur

1. Créer `backend/mcp_servers/mon_connecteur.py`
2. Hériter de `BaseConnector`
3. Implémenter `fetch_records()` et `_perform_health_check()`
4. Renvoyer des `UnifiedRecord` avec les noms de colonnes d'origine dans le payload
5. Ajouter les tests dans `tests/test_connectors.py`

### Ajouter une règle

Via l'API (`POST /api/v1/rules`, éventuellement à partir d'un brouillon de `POST /api/v1/rules/from-text`), ou,
pour une règle prédéfinie, en ajoutant `data/rules/r_ma_regle.json` (format ci-dessus) puis en lançant
`python -m engine.validate_rules`. Le seed l'insère au prochain démarrage.

---

**Phase** : P2 (moteur de règles), en cours. Faits : interpréteur, normaliseur, API règles et corrélations,
limitation par IP et conversion NL→règle implémentés. Extensions du DSL en attente.
