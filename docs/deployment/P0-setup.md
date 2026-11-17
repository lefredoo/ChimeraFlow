# Guide de mise en place P0

## Phase P0 : Fondations, terminée côté dépôt

**Dates :** 13 et 14 novembre 2026
**Durée prévue :** 8 heures
**Statut :** ✓ terminée dans le dépôt. Les points qui ne se vérifient pas dans le dépôt (déploiement, Vercel, Dokploy) sont listés dans `.kiro/specs/chimeraflow-backend/tasks.md`.

---

## Ce qui a été construit

### Backend (FastAPI)
- ✓ API principale avec contrôle de santé (`GET /health`) et routeur des sources (`/api/v1/sources`)
- ✓ Conteneur Docker (limite mémoire 384 Mo, 0,5 CPU dans `docker-compose.yml`)
- ✓ Journalisation standard (`logging.basicConfig`, format texte)
- ✓ Configuration CORS (liste blanche)
- ✓ Base de tests
- ✓ Script de test `spike_access.py` pour la lecture des fichiers .mdb

### Frontend (Next.js)
- ✓ Page d'accueil de test qui appelle `GET /health` de l'API
- ✓ Polices IBM Plex chargées depuis Google Fonts (`frontend/app/globals.css`)
- ✓ Tailwind CSS (dépendance en version 4)
- ✓ Mise en page responsive (grille à trois colonnes à partir de la taille `md`)

### Infrastructure
- ✓ Docker Compose : API et Redis
- ✓ Limites mémoire et CPU par conteneur
- ✓ Health checks de l'API et de Redis
- ✓ Volume de données monté en lecture seule (`./data:/data:ro`)

### Artefacts Kiro
- ✓ 3 specs : `connectors-spec.md`, `rule-engine-spec.md` (dossier `chimeraflow-backend/`) et l'interface (`chimeraflow-ui/design.md`, ancien `ui-spec.md`)
- ✓ 2 fichiers de steering : `connectors.md`, `security.md`
- ✓ Hooks de test et de validation dans `.kiro/hooks/` (ajoutés en P1)
- ✗ `.kiro/agents/` : prévu en P3, non créé

### Génération de données
- ✓ Générateur Excel (`scripts/generate_excel.py` → `tarifs_fournisseurs.xlsx`)
- ✓ Générateur WhatsApp (`scripts/generate_whatsapp.py` → `commandes_clients.txt`)
- ✓ Générateur Mobile Money (`scripts/generate_momo.py` → `momo_transactions.csv`)
- ✓ Variantes volontaires pour tester la normalisation

---

## Mise en place locale

### Prérequis
- Python 3.13 et [uv](https://docs.astral.sh/uv/)
- Node.js 18.18 ou plus récent (Next.js 15)
- Docker et Docker Compose (tests complets et Redis)

### Générer les données synthétiques

```powershell
python scripts/generate_excel.py          # requiert pandas et openpyxl
python scripts/generate_whatsapp.py
python scripts/generate_momo.py
cscript //Nologo scripts/generate_access_windows.vbs   # Windows avec Access uniquement
```

### Installer le backend

```powershell
cd backend
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

### Configurer l'environnement

Il n'existe pas de `.env.example`. Le backend lit des variables d'environnement (`config.py`). La liste complète est dans `AGENTS.md` §22.

En production, le seul fichier local est un `.env` à la racine qui contient `DOPPLER_TOKEN`. Toutes les autres variables viennent de Doppler.

Pour un lancement local, exporter les variables requises dans le shell (PowerShell) :

```powershell
$env:DATABASE_URL = "postgresql://user:pass@host/dbname"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:DATA_DIR = "../data"
$env:ACCESS_READER = "access-parser"
$env:RATE_LIMIT_PER_IP = "10"
$env:RATE_LIMIT_WINDOW_SECONDS = "60"
```

### Lancer le backend

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
# API : http://localhost:8000
# Documentation : http://localhost:8000/docs (exige BACKEND_NODE_ENV=development)
```

### Lancer le frontend

```powershell
cd frontend
npm install
npm run dev
# Application : http://localhost:3000
```

`NEXT_PUBLIC_API_URL` indique l'adresse de l'API. Sans cette variable, la page utilise `http://localhost:8000` codé en dur (écart à `AGENTS.md` §7, voir `TECH_DEBT.md`).

### Lancer avec Docker Compose

```powershell
docker compose up -d
docker compose logs -f
docker compose down
```

`docker-compose.yml` exige `DATABASE_URL`, `REDIS_PASSWORD`, `RATE_LIMIT_PER_IP`, `RATE_LIMIT_WINDOW_SECONDS`, `AUTH_TOKEN_SECRET`, `DEMO_LOGIN_EMAIL` et `DEMO_LOGIN_PASSWORD_HASH`. Redis n'expose aucun port sur l'hôte.

---

## Test d'accès à Access (spike)

**Statut :** réalisé. `data/STOCK_ZOBO.mdb` existe, et la table `Articles` est lue par le lecteur Python `access-parser` (`backend/tests/test_access_readers.py`).

```powershell
cd backend
.venv\Scripts\python.exe spike_access.py
```

**Choix retenu :** `access-parser` pour le développement sous Windows, `mdbtools` (CLI `mdb-export`) dans l'image Docker de production. Les deux lecteurs sont comparés quand `mdb-export` est installé (tests sautés sinon).

---

## Points de contrôle

- [x] Trois specs présentes dans `.kiro/specs/`
- [x] Fichiers de données synthétiques présents dans `data/`
- [x] Script de test Access présent (`backend/spike_access.py`)
- [ ] `docker compose up -d` démarre sans erreur (non vérifié dans ce document)
- [ ] `curl http://localhost:8000/health` renvoie 200 (non vérifié dans ce document)
- [ ] La page d'accueil affiche l'état de l'API (non vérifié dans ce document)
- [ ] `redis-cli ping` répond `PONG` (non vérifié dans ce document)

---

## Critères de sortie P0

- ✓ **Bout en bout** : la page d'accueil interroge `GET /health` de l'API. Déploiement en production : non vérifié dans le dépôt.
- ✓ **Spike Access** : `STOCK_ZOBO.mdb` présent, lecture validée par tests.
- ✓ **3 specs** présentes : connectors, rule-engine, ui. Leur approbation n'est pas tracée dans le dépôt.

---

## Phase suivante

**P1 Connecteurs** : terminée côté code (4 connecteurs, enregistrement unifié, tests de contrat). Les serveurs MCP restent à faire.
**P2 Moteur de règles** : en cours. Voir `.kiro/specs/chimeraflow-backend/tasks.md`.

---

## Notes de déploiement

### Vercel (frontend)
- Commande de build : `cd frontend && npm run build`
- Dossier de sortie : `frontend/.next`
- Variable : `NEXT_PUBLIC_API_URL`

### VPS Hetzner (backend via Dokploy)
- Dockerfile : `backend/Dockerfile` (cible `runtime`, par défaut)
- Port : 8000
- Redis : service géré ou conteneur séparé
- Volume : `/data` en lecture seule

**Les étapes de déploiement manuel seront documentées en P4.**

---

Construit pour le Kiroween 2026 | Démonstration ZOBO Hardware Store
