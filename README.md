# ChimeraFlow

> Assembler Excel, Access et WhatsApp en une vue corrélée pour les petites entreprises.

**Projet du Kiroween 2026 Hackathon** | Catégorie : Frankenstein | Projet solo | P0 et P1 terminées, P2 en cours

---

## 🎯 Qu'est-ce que ChimeraFlow ?

Les petites entreprises ne travaillent pas avec des API. Elles travaillent avec des **tableurs Excel**, des **bases Access** et des **groupes WhatsApp**. ChimeraFlow relie ces sources disjointes grâce à des règles de corrélation écrites en français ou en anglais.

**Scénario de démonstration :** quincaillerie fictive ZOBO (Douala, Cameroun). Toutes les données sont synthétiques.
- **Base Access** (`data/STOCK_ZOBO.mdb`) : stock hérité, table `Articles`
- **Tableur Excel** (`data/tarifs_fournisseurs.xlsx`) : tarifs fournisseurs, mise en forme imparfaite, accents manquants, feuille `Tarifs`
- **Export WhatsApp** (`data/commandes_clients.txt`) : groupe de commandes, mélange français et anglais, abréviations
- **Mobile Money** (`data/momo_transactions.csv`) : confirmations de paiement

**Point clé :** un même produit peut être écrit de quatre façons (`ciment 50 kg`, `Ciment50kg`, `cimént 50kg`, `ciment (50kg)`). La normalisation les ramène à la même clé (`ciment 50 kg`), sans corriger les nombres : `ciment 50 kg` ne correspond jamais à `ciment 40 kg`.

---

## 🚀 Démarrage rapide

### Prérequis
- Python 3.13 et [uv](https://docs.astral.sh/uv/) (installation du backend)
- Node.js 18.18 ou plus récent (Next.js 15, frontend)
- Docker (tests complets avec mdbtools, et Redis)
- Doppler CLI (facultatif, gestion des secrets)

### 1. Cloner et préparer les données

```powershell
git clone https://github.com/lefredoo/ChimeraFlow.git
cd ChimeraFlow

# Régénérer les données synthétiques si besoin (les quatre fichiers sont déjà dans data/)
python scripts/generate_excel.py          # requiert pandas et openpyxl
python scripts/generate_whatsapp.py
python scripts/generate_momo.py           # déterministe : même sortie à chaque exécution
cscript //Nologo scripts/generate_access_windows.vbs   # Windows avec Access uniquement
```

### 2. Installer le backend

```powershell
cd backend
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

`requirements.txt` contient les dépendances d'exécution. `requirements-dev.txt` ajoute pytest, Hypothesis, ruff et les outils de test. L'environnement `backend/.venv` est ignoré par Git.

### 3. Configurer l'environnement

Il n'existe **pas de `.env.example`**. Le backend lit uniquement des variables d'environnement, sans chargeur de `.env`. La liste complète, avec les variables obligatoires et facultatives, est dans `AGENTS.md` §22.

- **Un seul fichier `.env` local, à la racine** (non versionné) : en production, il ne contient que `DOPPLER_TOKEN`. Toutes les autres variables viennent de Doppler.
- Pour un lancement local, exporter les variables requises dans le shell, par exemple :

```powershell
$env:DATABASE_URL = "postgresql://user:pass@host/dbname"   # PostgreSQL (Neon en production)
$env:CORS_ORIGINS = "http://localhost:3000"
$env:DATA_DIR = "../data"
$env:ACCESS_READER = "access-parser"              # Windows : pas de mdbtools
$env:REDIS_URL = "redis://localhost:6379/0"
$env:RATE_LIMIT_PER_IP = "10"
$env:RATE_LIMIT_WINDOW_SECONDS = "60"
$env:AUTH_TOKEN_SECRET = "<au moins 32 caractères aléatoires>"
$env:DEMO_LOGIN_EMAIL = "demo@example.com"
$env:DEMO_LOGIN_PASSWORD_HASH = "<sortie de : python -m auth.hash_password>"   # voir backend/README.md, Authentification
```

Une variable requise absente arrête l'application au démarrage, c'est voulu (AGENTS.md §7).

### 4. Créer le schéma et lancer l'API

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

- Documentation interactive : http://localhost:8000/docs (non servie quand `BACKEND_NODE_ENV=production`)
- Santé : http://localhost:8000/health

Tous les endpoints `/api/v1` exigent un jeton Bearer, obtenu par `POST /api/v1/auth/login` avec le compte de démonstration.

### 5. Lancer le frontend

```powershell
cd frontend
npm install
npm run dev     # http://localhost:3000
```

Le frontend exige `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_LOGIN_EMAIL` et `NEXT_PUBLIC_DEMO_LOGIN_PASSWORD` au build (le compte de démonstration est public : la page `/login` l'affiche). La page d'accueil redirige vers `/login` sans session.

### Docker Compose

```powershell
docker compose up -d
```

Le fichier `docker-compose.yml` démarre l'API (port 8000) et Redis (sans port publié). Il exige `DATABASE_URL`, `REDIS_PASSWORD`, `RATE_LIMIT_PER_IP`, `RATE_LIMIT_WINDOW_SECONDS`, `AUTH_TOKEN_SECRET`, `DEMO_LOGIN_EMAIL` et `DEMO_LOGIN_PASSWORD_HASH`. L'API applique les migrations avant de servir les requêtes (point d'entrée du conteneur, voir `backend/Dockerfile`).

---

## 🧪 Tests

Depuis `backend/`, sous Windows :

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m ruff check .
```

Sans mdbtools (Windows), les tests qui exigent `mdb-export` sont sautés (3 sautés). La suite complète, mdbtools inclus, tourne dans l'image Docker de test, depuis la racine du dépôt :

```powershell
docker build --target test -t chimeraflow-backend-test backend; docker run --rm -v "${PWD}/data:/data:ro" chimeraflow-backend-test
```

Détail des tests : `backend/tests/README.md`.

---

## 📋 Avancement

| Phase | Statut | Contenu |
|-------|--------|---------|
| P0 Fondations | ✅ terminée | Structure, API de santé, page d'accueil, Docker Compose, specs, steering, données synthétiques, spike Access |
| P1 Connecteurs | ✅ terminée côté code | Excel, Access, WhatsApp, Mobile Money ; enregistrement unifié ; tests de contrat ; API `sources` |
| P2 Moteur de règles | 🔄 en cours | Normaliseur, interpréteur avec provenance, 5 règles prédéfinies (3 désactivées), API règles et corrélations, migrations Alembic, limitation par IP, conversion NL→règle, budget LLM |
| P3 Interface et Crew | ⏳ à faire | Tableau de bord, composeur de règles, connecteur n°4 |
| P4 Durcissement | ⏳ à faire | Tests de production, scan de secrets |
| P5 Soumission | ⏳ à faire | Vidéo, write-up, blog |

**Reste à faire en P2 :** connexion à un vrai proxy LiteLLM (clé, URL et modèle), configuration Doppler et branche Neon de développement, CI GitHub Actions (bloquée par la facturation du compte), déploiement et pull request `dev` → `main`. Détail : `.kiro/specs/tasks.md`.

**Limites connues :** une seule entité par message ; une règle ne peut pas encore filtrer sur le record déclencheur, donc trois règles prédéfinies restent désactivées ; la comparaison de noms porte sur la chaîne entière ; le parseur WhatsApp ne lit que le format Android. Liste complète : `docs/decisions/TECH_DEBT.md`.

---

## 📁 Structure du dépôt

```
.
├── backend/                  # API FastAPI (Python 3.13)
│   ├── main.py               # point d'entrée de l'API
│   ├── config.py             # lecture et validation des variables d'environnement
│   ├── api/                  # routeurs sources, rules, correlations ; limitation ; erreurs
│   ├── engine/               # normaliseur, interpréteur, règles prédéfinies, NL→règle, budget
│   ├── mcp_servers/          # connecteurs Excel, Access, WhatsApp, Mobile Money
│   ├── models/               # modèles SQLAlchemy et seed des règles
│   ├── schemas/              # schémas Pydantic (règles, réponses)
│   ├── migrations/           # migrations Alembic (0001, 0002)
│   ├── tests/                # suite de tests (voir tests/README.md)
│   ├── spike_access.py       # test de lecture d'un .mdb
│   ├── Dockerfile            # cibles base, test et runtime
│   ├── requirements.txt      # dépendances d'exécution
│   └── requirements-dev.txt  # dépendances de test et de lint
├── frontend/                 # Next.js 15 (App Router) : page d'accueil de test
├── data/                     # données synthétiques (montées en lecture seule dans Docker)
│   ├── STOCK_ZOBO.mdb
│   ├── tarifs_fournisseurs.xlsx
│   ├── commandes_clients.txt
│   ├── momo_transactions.csv
│   └── rules/                # cinq règles prédéfinies, une par fichier JSON
├── scripts/                  # générateurs de données synthétiques
├── docs/                     # documentation du projet (décisions, déploiement, journal)
├── .kiro/                    # configuration Kiro
│   ├── specs/                # connectors, rule-engine, ui, api, design, tasks
│   ├── steering/             # connectors.md, security.md
│   └── hooks/                # parser-test, rule-validate, spec-update-reminder
├── .github/workflows/ci.yml  # CI : lint, tests, image Docker de test, migrations PostgreSQL
├── docker-compose.yml        # API et Redis
├── doppler.yaml              # configuration du projet Doppler
├── AGENTS.md                 # règles de développement pour les agents IA
├── DESIGN.md                 # système de design
├── CLAUDE.md                 # instructions pour Claude
├── LICENSE                   # MIT, LinguaSolution LLC
├── README.md                 # ce fichier
└── Roadmap.md                # plan produit (84 h sur 21 jours)
```

---

## 🔧 Fonctionnalités

### 1. Corrélation de données multi-sources
- Enregistrement unifié pour toutes les sources (`source`, `source_ref`, `timestamp`, `lang`, `entities`, `payload`)
- Normalisation : casse, accents, espaces, nombres conservés, synonymes FR/EN
- Provenance : chaque corrélation liste les records source qui l'ont produite

### 2. Moteur de règles déclaratives
- Règles en JSON, validées par Pydantic ; aucune exécution de code
- Opérateurs en liste blanche : `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`
- Conversion d'une phrase en brouillon de règle par LiteLLM (2 relances au plus, le brouillon n'est pas stocké)
- Budget LLM plafonné, puis repli sur les règles prédéfinies

### 3. Connecteurs
- **Excel** : lecture de `tarifs_fournisseurs.xlsx` (feuille `Tarifs`) avec pandas et openpyxl
- **Access** : lecture de `STOCK_ZOBO.mdb` par `mdbtools` (Docker) ou `access-parser` (Python pur, Windows)
- **WhatsApp** : parseur du format d'export Android ; les autres lignes sont comptées comme erreurs
- **Mobile Money** : lecture du CSV ; les lignes invalides sont ignorées et comptées

Les connecteurs sont aujourd'hui des classes Python appelées par l'API. Ils ne sont pas encore exposés comme serveurs MCP.

### 4. Tests basés sur les propriétés (Hypothesis)
Six propriétés de correction (P1 à P6) sont définies dans `.kiro/specs/design.md` §12. Statut à ce jour :
- **P2** (idempotence de la normalisation) : couverte
- **P1** (provenance), **P4** (déterminisme), **P6** (pas de fabrication) : partielles, tests sur exemples
- **P3** (aller-retour du parseur) et **P5** (monotonie de la fenêtre) : non couvertes

---

## 🎨 Système de design

**Style :** moderne, effet verre (glassmorphism)
**Palette :** bleu professionnel (`#2563eb` principal)
**Typographie :** IBM Plex Sans (interface), IBM Plex Serif (titres), IBM Plex Mono (code)

Voir [DESIGN.md](./DESIGN.md).

---

## 🤖 Usage de Kiro

1. **Specs** : `.kiro/specs/` contient les specs des connecteurs, du moteur de règles, de l'interface, de l'API, la conception (`design.md`) et le plan (`tasks.md`).
2. **Steering** : conventions des connecteurs et règles de sécurité (`.kiro/steering/`).
3. **Hooks** : `parser-test` (tests de contrat et PBT à la sauvegarde d'un connecteur), `rule-validate` (validation d'un fichier de `data/rules/`), `spec-update-reminder`.
4. **Kiro Crew** : trois agents prévus en P3 (`chimera-builder`, `test-warden`, `rule-smith`), pas encore créés.
5. **Serveurs MCP** : prévus, `.kiro/settings/mcp.json` n'existe pas encore.

---

## 📚 Documentation

- **[AGENTS.md](./AGENTS.md)** : règles de développement pour les agents IA (en anglais, par choix)
- **[DESIGN.md](./DESIGN.md)** : système de design
- **[Roadmap.md](./Roadmap.md)** : plan produit, P0 à P5 (84 h sur 21 jours)
- **[docs/](./docs/)** : documentation détaillée
  - [docs/decisions/DECISIONS_LOG.md](./docs/decisions/DECISIONS_LOG.md) : décisions d'architecture
  - [docs/decisions/TECH_DEBT.md](./docs/decisions/TECH_DEBT.md) : dette technique
  - [docs/deployment/P0-setup.md](./docs/deployment/P0-setup.md) : guide d'installation et de vérification
  - [docs/build-log.md](./docs/build-log.md) : journal de bord
- **[.kiro/specs/](./.kiro/specs/)** : spécifications (API, conception, plan)

---

## 🎬 Démonstration

- **Vidéo :** à publier en P5 (moins de 3 minutes)
- **Application en ligne :** à publier. Aucune URL de démonstration n'est encore vérifiée.

**Scénario de démonstration :**
1. Afficher les trois sources de la quincaillerie ZOBO (Access, Excel, WhatsApp)
2. Créer une règle en français : « Quand un client demande un produit, afficher le stock et le prix »
3. Voir les cartes de corrélation avec leur provenance
4. Cas piège : le même produit écrit de quatre façons est reconnu dans tous les cas
5. Couper une source : l'interface se dégrade sans rien casser

---

## 🏢 À propos de LinguaSolution LLC

ChimeraFlow est développé par LinguaSolution LLC, à partir de son expertise en normalisation linguistique et en traitement du langage naturel sur des données multilingues et non structurées. Les mêmes techniques servent à corréler des données d'entreprise désordonnées.

---

## 🤝 Contribuer

Ce projet a été réalisé pour le Kiroween 2026 Hackathon. Les contributions pendant la période de jugement (jusqu'au 29 janvier 2027) peuvent affecter l'éligibilité.

1. Travailler sur la branche `dev`, jamais directement sur `main`
2. Suivre les [Conventional Commits](https://www.conventionalcommits.org/) (messages en anglais)
3. Lire `AGENTS.md` pour les conventions de code
4. Noter les décisions dans `docs/decisions/DECISIONS_LOG.md`

---

## 📄 Licence

Licence MIT, voir le fichier [LICENSE](./LICENSE).

Copyright (c) 2026 LinguaSolution LLC

---

## 📞 Contact

**Fondateur :** Fredy Zobo
**Organisation :** LinguaSolution LLC
**GitHub :** [@lefredoo](https://github.com/lefredoo)
**Hackathon :** Kiroween 2026

---

**Construit à Yaoundé, Cameroun 🇨🇲 | Propulsé par Kiro**
