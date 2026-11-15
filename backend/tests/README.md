# Tests du backend ChimeraFlow

Suite de tests des connecteurs MCP, du moteur de règles, de l'API et de la conversion NL→règle.

## Structure

```
tests/
├── __init__.py
├── conftest.py                 # variables d'environnement de test, profils Hypothesis, fixture api_client
├── factories.py                # records unifiés en mémoire (WhatsApp, Access, Excel)
├── test_api_correlations.py    # seed, exécution, clés étrangères, idempotence, cascade
├── test_connectors.py          # tests de contrat (R1 à R4)
├── test_access_readers.py      # choix de ACCESS_READER, équivalence mdbtools et access-parser
├── test_migrations.py          # alembic upgrade head / downgrade base, pas de dérive avec les modèles
├── test_connector_payloads.py  # noms de champs d'origine, entités produit, erreurs de parsing
├── test_properties.py          # tests basés sur les propriétés (Hypothesis), P1 à P6
├── test_normalizer.py          # variantes de normalisation, idempotence (P2), nombres
├── test_interpreter.py         # exécution des règles, provenance, conditions where
├── test_schemas.py             # validation du schéma de règle
├── test_rule_files.py          # chargement de data/rules/*.json (échec immédiat), CLI de validation
├── test_rate_limit.py          # 429 + Retry-After, IP client / proxys de confiance, variables requises
├── test_nl_to_rule.py          # NL→règle : relances, budget, désactivation, injection (LiteLLM simulé)
├── test_api_errors.py          # codes d'erreur stables de l'API
└── test_health.py              # contrôle de santé et endpoints de base
```

## Installation

Dans l'environnement virtuel Python 3.13 (`backend/.venv`), depuis `backend/` :

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

Sous Linux ou macOS, remplacer `.venv\Scripts\python.exe` par `.venv/bin/python`.

Ce fichier installe :
- `pytest` : lanceur de tests
- `pytest-asyncio` : tests asynchrones
- `hypothesis` : tests basés sur les propriétés
- `ruff` et `pyflakes` : lint

## Lancer les tests

### Tous les tests

```powershell
# Depuis backend/
.venv\Scripts\python.exe -m pytest tests -v
.venv\Scripts\python.exe -m ruff check .
```

Sous Windows, il n'y a pas de mdbtools : les tests qui exigent `mdb-export` sont sautés (3 sautés). Pour les exécuter, lancer la suite dans Docker.

### Tous les tests dans Docker (avec mdbtools, rien n'est sauté)

Depuis la racine du dépôt, en PowerShell (une seule ligne) :

```powershell
docker build --target test -t chimeraflow-backend-test backend; docker run --rm -v "${PWD}/data:/data:ro" chimeraflow-backend-test
```

En bash, remplacer `;` par `&&` et `${PWD}` par `$PWD`. Pour lancer le profil de CI, ajouter `python -m pytest tests -q --hypothesis-profile=ci` après le nom de l'image. L'étape `test` de `backend/Dockerfile` installe `requirements-dev.txt` par-dessus l'image d'exécution, qui fournit `mdb-export`.

### Un fichier, une classe ou une fonction

```powershell
.venv\Scripts\python.exe -m pytest tests\test_connectors.py -v
.venv\Scripts\python.exe -m pytest tests\test_properties.py -v
.venv\Scripts\python.exe -m pytest tests\test_connectors.py::TestConnectorContract -v
.venv\Scripts\python.exe -m pytest tests\test_properties.py::TestNormalizationProperties::test_normalization_idempotent -v
```

### Avec couverture

```powershell
.venv\Scripts\python.exe -m pytest tests --cov=mcp_servers --cov=engine --cov-report=html
```

(Requiert `pytest-cov`, qui n'est pas dans `requirements-dev.txt`.)

## Catégories de tests

### Tests de contrat (`test_connectors.py`)

Vérifient la conformité à `.kiro/specs/connectors-spec.md` :

- **R1** : tous les connecteurs implémentent `fetch_records()` et `health_check()`
- **R2** : les records respectent le schéma unifié
- **R3** : le contrôle de santé est mis en cache 30 secondes
- **R4** : les erreurs de parsing sont comptées, sans plantage

Le test de contrat Access tourne avec les deux lecteurs (`access-parser`, `mdbtools`). Le cas `mdbtools` et les tests d'équivalence des lecteurs (`test_access_readers.py`) sont sautés quand `mdb-export` n'est pas installé.

### Tests basés sur les propriétés (`test_properties.py`, `test_normalizer.py`)

Utilisent Hypothesis. Statut de chaque propriété de `Roadmap.md` §7 (détail dans `.kiro/specs/design.md` §12) :

- **P1** provenance : partielle
- **P2** idempotence de la normalisation : couverte (Hypothesis)
- **P3** aller-retour du parseur : non couverte (le test `TestRoundTrip` ne vérifie que des champs non vides)
- **P4** déterminisme : partielle (exemples fixes)
- **P5** monotonie de la fenêtre : non couverte
- **P6** absence de fabrication : partielle

### Tests du moteur et du schéma

- `test_interpreter.py` : exécute `r_low_stock` sur des records en mémoire (provenance, seuil, fenêtre temporelle, types incompatibles, choix du meilleur candidat parmi les doublons, rendu des templates sans expansion d'accolades)
- `test_normalizer.py` : vérifie aussi que des nombres différents ne correspondent jamais (`50 kg` contre `40 kg`) et que décimales et fractions restent un seul jeton
- `test_api_correlations.py` : utilise la fixture `api_client` (base SQLite en mémoire, lifespan de l'application, règles prédéfinies seedées) avec les connecteurs de fichiers remplacés par des records en mémoire. Les clés étrangères sont appliquées sur SQLite : ces tests échouent comme le ferait PostgreSQL.
- `test_schemas.py` : refuse les joins vides, les joins Excel sans `sheet`, les joins Access sans `table`, les opérateurs inconnus
- `test_connector_payloads.py` : le payload garde les noms de colonnes d'origine, MoMo émet une entité `product`, les lignes invalides sont sautées et comptées

Les nouveaux tests suivent le format « should [résultat] when [condition] ».

## Configuration

Configuration des tests dans `pytest.ini` :

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
addopts = --hypothesis-profile=dev
```

Profils Hypothesis enregistrés dans `tests/conftest.py` :

| Profil | `max_examples` | `deadline` |
|--------|----------------|------------|
| `dev` (défaut) | 100 | aucune |
| `ci` | 500 | 5000 ms |

Pour la CI :

```bash
python -m pytest tests/ --hypothesis-profile=ci
```

## Données de test

Les tests lisent les données synthétiques de `data/` :

- `data/commandes_clients.txt` : export WhatsApp
- `data/momo_transactions.csv` : CSV Mobile Money
- `data/tarifs_fournisseurs.xlsx` : tarifs Excel
- `data/STOCK_ZOBO.mdb` : base Access

Régénérer les fichiers manquants :

```powershell
# Depuis la racine du projet
python scripts/generate_excel.py
python scripts/generate_momo.py
cscript //Nologo scripts/generate_access_windows.vbs   # Windows avec Access uniquement
```

Le script VBS doit rester en ASCII seul (cscript le lit en ANSI) : les lettres accentuées sont écrites `\xHH` et décodées avec `ChrW`.

## Environnement

`tests/conftest.py` définit ces variables avant l'import de l'application. Aucun fichier `.env` n'est nécessaire.

| Variable | Valeur en test |
|----------|----------------|
| `BACKEND_NODE_ENV` | `test` (Redis non requis) |
| `DATA_DIR` | `<repo>/data` |
| `DATABASE_URL` | `sqlite://` (en mémoire) |
| `CORS_ORIGINS` | `http://localhost:3000` |
| `ACCESS_READER` | `access-parser` (le lecteur mdbtools est construit explicitement dans les tests) |
| `RATE_LIMIT_PER_IP`, `RATE_LIMIT_WINDOW_SECONDS` | `1000`, `60` (les tests de 429 abaissent la limite ; le limiteur utilise le stockage mémoire car `BACKEND_NODE_ENV=test`) |
| `AUTH_TOKEN_SECRET`, `DEMO_LOGIN_EMAIL`, `DEMO_LOGIN_PASSWORD_HASH` | valeurs de test (`tests/demo_account.py`) ; le hash est calculé à chaque exécution avec un sel neuf. La fixture `api_client` envoie un jeton valide, `anonymous_client` n'en envoie pas |
| `LITELLM_*`, `TRUSTED_PROXIES`, `RATE_LIMIT_NL_PER_IP`, `RATE_LIMIT_LOGIN_PER_IP` | retirés de l'environnement (la conversion NL→règle se configure par test ; seul `litellm.acompletion` est simulé) |

## Intégration avec les hooks Kiro

Quand un fichier de connecteur est sauvegardé, le hook `parser-test` lance :

```bash
python -m pytest tests/test_connectors.py tests/test_properties.py -v --tb=short
```

Défini dans `.kiro/hooks/parser-test.json`.

## Dépannage

### `ModuleNotFoundError: No module named 'hypothesis'`

Installer les dépendances de test dans l'environnement virtuel :

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

### `ValueError: Required environment variable '...' is not set`

L'application est importée hors de pytest. Exporter les variables de `backend/README.md` (section Configuration) ou lancer les tests avec `python -m pytest`.

### Fichiers de données introuvables

Régénérer les données synthétiques (voir la section Données de test).

---

_Dernière mise à jour : 2026-11-14_
